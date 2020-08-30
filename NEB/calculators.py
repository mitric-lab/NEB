#!/usr/bin/env python
"""
functions for submitting QChem or Gaussian jobs to the queue,
requires the scripts 'run_gaussian_09.sh', 'run_gaussian_16.sh' and 'run_qchem.sh'
"""
from __future__ import print_function
from __future__ import absolute_import
from builtins import map
from builtins import range
from NEB import XYZ, AtomicData
from NEB.Gaussian2py import Checkpoint

import numpy as np
import os
import subprocess
from collections import OrderedDict
import json

def run_gaussian_09(atomlist, directory=".", nprocs=1, mem="6Gb"):
    """
    run Gaussian input script in `neb.gjf` and read energy and gradient
    from checkpoing file `grad.fchk`.

    Parameters
    ----------
    atomlist:  list of tuples with atomic numbers and cartesian positions (Zat,[x,y,z])
               for each atom
    directory: directory where the calculation should be performed

    Optional
    --------
    nprocs : int, number of processors
    mem    : str, allocated memory (e.g. '6Gb', '100Mb')

    Returns
    -------
    en    :  total energies of ground state (in Hartree)
    grad  :  gradient of total energy (in a.u.)
    """
    # create directory if it does not exist already
    os.system("mkdir -p %s" % directory)
    os.system("cp neb.gjf %s/neb.gjf" % directory)
    # update geometry
    XYZ.write_xyz("%s/geometry.xyz" % directory, [atomlist])
    # remove number of atoms and comment
    os.system("cd %s; tail -n +3 geometry.xyz > geom" % directory)
    # calculate electronic structure
    #print "running Gaussian..."
    # submit calculation to the cluster
    ret  = os.system(r"cd %s; run_gaussian_09.sh --wait --fchk neb.gjf %d %s" % (directory, nprocs, mem))
    assert ret == 0, "Return status = %s, error in Gaussian calculation, see %s/neb.out!" % (ret, directory)
    # read checkpoint files
    data = Checkpoint.parseCheckpointFile("%s/grad.fchk" % directory)

    en   = data["_Total_Energy"]
    grad = data["_Cartesian_Gradient"]

    ### DEBUG
    # print("Cartesian Gaussian 09 gradient in %s" % directory)
    # print(grad)
    ###

    return en, grad

def run_gaussian_16(atomlist, directory=".", nprocs=1, mem="6Gb"):
    """
    run Gaussian input script in `neb.gjf` and read energy and gradient
    from checkpoing file `grad.fchk`.

    Parameters
    ----------
    atomlist:  list of tuples with atomic numbers and cartesian positions (Zat,[x,y,z])
               for each atom
    directory: directory where the calculation should be performed

    Optional
    --------
    nprocs : int, number of processors
    mem    : str, allocated memory (e.g. '6Gb', '100Mb')

    Returns
    -------
    en    :  total energies of ground state (in Hartree)
    grad  :  gradient of total energy (in a.u.)
    """
    # create directory if it does not exist already
    os.system("mkdir -p %s" % directory)
    os.system("cp neb.gjf %s/neb.gjf" % directory)

    with open("%s/neb.gjf" % directory, "w") as new_file:
        with open("%s/neb.gjf" % directory,) as old_file:
            lines = old_file.readlines()
            try:
                index = lines.index("@geom\n")
            except:
                index = 9
            lines.remove("@geom\n")
            c = AtomicData.bohr_to_angs
            for idx, (Zat, pos) in enumerate(atomlist):
                l = "%2s    %+12.10f   %+12.10f   %+12.10f \n" % (AtomicData.atom_names[Zat-1].upper(), pos[0]*c, pos[1]*c, pos[2]*c)
                lines.insert(idx + index, l)
        new_file.writelines(lines)
    # update geometry
    XYZ.write_xyz("%s/geometry.xyz" % directory, [atomlist])
    #XYZ.write_geom("%s/geom" % directory, [atomlist])
    # remove number of atoms and comment
    #os.system("cd %s; tail -n +3 geometry.xyz > geom" % directory)
    # calculate electronic structure
    #print "running Gaussian..."
    # submit calculation to the cluster
    ret  = os.system(r"cd %s; run_gaussian_16.sh --wait --fchk neb.gjf %d %s" % (directory, nprocs, mem))
    assert ret == 0, "Return status = %s, error in Gaussian calculation, see %s/neb.out!" % (ret, directory)
    # read checkpoint files
    data = Checkpoint.parseCheckpointFile("%s/grad.fchk" % directory)

    en   = data["_Total_Energy"]
    grad = data["_Cartesian_Gradient"]

    ### DEBUG
    # print("Cartesian Gaussian 09 gradient in %s" % directory)
    # print(grad)
    ###

    return en, grad


def run_qchem(atomlist, directory=".", nprocs=1, mem="6Gb"):
    """
    run QChem input script in `neb.in` and read energy and gradient
    from checkpoing file `neb.fchk`.

    Parameters
    ----------
    atomlist:  list of tuples with atomic numbers and cartesian positions (Zat,[x,y,z])
               for each atom
    directory: directory where the calculation should be performed

    Optional
    --------
    nprocs : int, number of processors
    mem    : str, allocated memory (e.g. '6Gb', '100Mb')

    Returns
    -------
    en    :  total energies of ground state (in Hartree)
    grad  :  gradient of total energy (in a.u.)
    """
    # create directory if it does not exist already
    os.system("mkdir -p %s" % directory)
    qchem_file = "%s/neb.in" % directory
    os.system("cp neb.in %s" % qchem_file)
    # update geometry
    geom_lines = []
    c = AtomicData.bohr_to_angs
    for Zat,pos in atomlist:
        l = "%2s    %+12.10f   %+12.10f   %+12.10f \n" % (AtomicData.atom_names[Zat-1].upper(), pos[0]*c, pos[1]*c, pos[2]*c)
        geom_lines.append(l)

    with open(qchem_file) as fh:
        lines = fh.readlines()

    # excise old geometry block
    start = None
    end = None
    for i,l in enumerate(lines):
        if "$molecule" in l:
            start = i
        elif "$end" in l and not (start is None):
            end = i
            break
    # replace old geometry by new one, the charge and multiplicity
    # in line start+1 is left as is.
    lines = lines[0:start+2] + geom_lines + lines[end:]

    with open(qchem_file, "w") as fh:
        for l in lines:
            fh.write(l)

    # calculate electronic structure
    #print "running QChem ..."
    # submit calculation to the cluster
    ret  = os.system(r"cd %s; run_qchem.sh --wait neb.in %d %s" % (directory, nprocs, mem))
    assert ret == 0, "Return status = %s, error in QChem calculation, see %s/neb.out!" % (ret, directory)

    # total energy is not saved in the checkpoint file, grep it from output file
    en = subprocess.check_output("cd %s; grep 'Total energy' neb.out | awk '{print $9}'" % directory, shell=True).strip()
    assert en != "", "Total energy not found in QChem output, see %s/neb.out!" % directory
    en = float(en)

    # read gradient from checkpoint files
    data = Checkpoint.parseCheckpointFile("%s/neb.fchk" % directory)
    grad = (-1.0) * data["_Cartesian_Forces"]

    ### DEBUG
    # print("Cartesian QChem gradient in %s" % directory)
    # print(grad)
    ###

    return en, grad

def run_bagel(atomlist, directory=".", nprocs=1, mem="6Gb"):
    """
    run BAGEL input script in `neb.json` and read energy and gradient back in.

    Parameters
    ----------
    atomlist:  list of tuples with atomic numbers and cartesian positions (Zat,[x,y,z])
               for each atom
    directory: directory where the calculation should be performed

    Optional
    --------
    nprocs : int, number of processors
    mem    : str, allocated memory (e.g. '6Gb', '100Mb')

    Returns
    -------
    en    :  total energies of ground state (in Hartree)
    grad  :  gradient of total energy (in a.u.)
    """
    # create directory if it does not exist already
    os.system("mkdir -p %s" % directory)
    bagel_file = "%s/neb.json" % directory
    os.system("cp neb.json %s" % bagel_file)
    # update geometry
    # load input from template
    with open(bagel_file, "r") as f:
        input_sec = json.load(f)
    # find molecule section
    for sec in input_sec["bagel"]:
        if sec["title"] == "molecule":
            molecule_sec = sec
            break
    else:
        raise RuntimeError("Molecule section not found in JSON template!")

    # The geometry in the 'molecule' section is replaced with the current one
    molecule_sec["angstrom"] = True

    # replace geometry with current coordinates
    natoms = len(atomlist)
    molecule_sec["geometry"] = []
    for i in range(0, natoms):
        atom = OrderedDict()
        Z,pos = atomlist[i]
        atom["atom"] = AtomicData.atom_names[Z-1].capitalize()
        atom["xyz"] = list(pos)
        molecule_sec["geometry"].append(atom)

    with open(bagel_file, "w") as fh:
        json.dump(input_sec, fh, indent=4)

    # calculate electronic structure
    #print "running BAGEL ..."
    # submit calculation to the cluster
    ret  = os.system(r"cd %s; run_bagel.sh neb.json %d %s --wait" % (directory, nprocs, mem))
    assert ret == 0, "Return status = %s, error in BAGEL calculation, see %s/neb.out!" % (ret, directory)

    # read energy and gradient (called "forces" in BAGEL, Arrrg)
    grad = np.zeros(3*natoms)
    with open("%s/FORCE.out" % directory) as fh:
        # First line contains energy (in Hartree)
        en = float(fh.readline())
        # skip one line
        fh.readline()
        # read gradients on atoms
        for i in range(0, natoms):
            parts = fh.readline().split()
            x,y,z = list(map(float, parts[1:4]))
            grad[3*i:3*(i+1)] = x,y,z

    return en, grad


def get_calculator(name):
    """
    retrieve function for calculating electronic structure (energy + gradient)
    """
    if name == "g09":
        return run_gaussian_09
    elif name == "g16":
        return run_gaussian_16
    elif name == "qchem":
        return run_qchem
    elif name == "bagel":
        return run_bagel
    else:
        raise ValueError("Unknown calculator '%s'" % name)
