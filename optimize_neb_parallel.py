#!/usr/bin/env python
"""
Optimize a reaction path using the nudged elastic band algorithm. An electronic structure
method implemented in Gaussian 09 is used to drive the calculation.

Nudged elastic band (NEB) method for finding minimum energy paths (MEP) and saddle points.
Implementation based on 
     "Improved tangent estimate in the nudged elastic band method for finding minimum energy paths and saddle points" by Henkelman, G.; Jonsson, H. J.Chem.Phys. 113, 9978 (2000) 
"""
from DFTB import XYZ, utils, AtomicData
from DFTB import optparse

from numpy import zeros, cos, sin, pi, linspace, array, dot, vstack, cumsum, argmin, frompyfunc, sign

from neb.calculators import get_calculator

import numpy as np
import numpy.linalg as la
from numpy.linalg import norm
from multiprocessing import Pool
import itertools

import os.path

# This is a wrapper function for making run_calculator compatible with Pool.map(...)
# The run_calculator() function has to be defined at the top level.
def run_calculator_map(args):
    atomlist, directory, kwds = args
    return run_calculator(atomlist, directory=directory, **kwds)


class NEB:
    def __init__(self, force_constant=1.0, force_constant_surface_switch=5.0, mass=1.0,
                 procs_per_image=1, parallel_images=1,
                 mem_per_image="6Gb",
                 scratch_dir="/scratch",
                 calculator="g09",
                 print_every=1):
        """
        Parameters
        ==========
        print_every: write path and energies for every N-th optimization step
        """
        self.force_constant = 1.0
        self.force_constant_surface_switch = force_constant_surface_switch
        self.mass = 1.0
        # parallelization
        self.procs_per_image = procs_per_image
        self.parallel_images = parallel_images
        # memory per job
        self.mem_per_image = mem_per_image
        
        self.scratch_dir = os.path.expandvars(scratch_dir)
        print "Subfolders for images will be created in the scratch directory '%s'" % self.scratch_dir
        print "Calculator is '%s'" % calculator

        # run_calculator() has to be defined as a global variable so that it can be pickled
        global run_calculator
        run_calculator = get_calculator(calculator)        
        
        self.print_every = print_every
        
        self.V = []
        self.istep = 0
    def setGeometry(self, atomlist):
        """
        Parameters:
        ===========
        atomlist    :  list of tuples (Zat,[x,y,z]) with atomic number and cartesian
                       coordinates in bohr for each atom
        """
        self.atomlist = atomlist
    def setName(self, name):
        """name is appended to the output files"""
        self.name = name
    def setImages(self, images, states):
        """
        Parameters:
        ===========
        images: list of numpy arrays with the coordinates of each image. If no intermediate states
           along the reaction coordinate are known, this has to be at least [initial_position, final_positions]
        states: list of indeces indicating on which electronic state the images reside
        """
        #self.R = [array(img) for img in images] # make sure we have numpy arrays
        self.R = images # vectors of atom positions
        self.states = states
    def addImagesLinearly(self, nimg=10):
        """
        between segments interpolate linearly. Add nimg additional images
        to each segments. If there are initially only two segments, the products
        and the educts, this creates a path of lengths nimg+2.
        """
        path = []
        st = []
        for i,Ri in enumerate(self.R[:-1]):
            for j,a in enumerate(linspace(0.0, 1.0, nimg)):
                Rinterp = (1.0-a)*self.R[i] + a*self.R[i+1]
                # 
                if j < nimg/2.0:
                    st.append( self.states[i] )
                else:
                    st.append( self.states[i+1] )
                if j < nimg-1: # do not append the last image
                    path.append(Rinterp)
        path.append(self.R[-1])
        st.append(self.states[-1])
        print "initial guess for path contains %s images" % len(path)
        self.R = path
        self.states = st
    def _getPES(self):
        """calculate energies and gradients at the image positions"""
        self.V = [None for Ri in self.R]  # potential energies of each image
        self.F = [None for Ri in self.R]  # true forces acting on each image

        # additional keywords controlling electronic structure calculation
        kwds = { "nprocs" : self.procs_per_image,
                 "mem": self.mem_per_image }
        
        if self.parallel_images > 1:
            # parallelize over images
            atomlists = [XYZ.vector2atomlist(x, self.atomlist) for x in self.R]
            image_dirs = ["IMAGE_%2.2d" % i for i in range(0, len(self.R))]
            image_dirs = [os.path.join(self.scratch_dir, d) for d in image_dirs]
            pool = Pool(self.parallel_images)
            results = pool.map(run_calculator_map, zip(atomlists, image_dirs, itertools.repeat(kwds, len(self.R))))
            for i,(en,grad) in enumerate(results):
                print "image %4.1d   energy= %+e   |grad|= %e" % (i,en, la.norm(grad))
                self.V[i] = en
                self.F[i] = -grad
        else:
            # sequential implementation
            for i,Ri in enumerate(self.R):
                atomlist = XYZ.vector2atomlist(Ri, self.atomlist)
                image_dir = os.path.join(self.scratch_dir, "IMAGE_%2.2d" % i)
                en, grad = run_calculator(atomlist, directory=image_dir, **kwds)
                self.V[i] = en
                self.F[i] = - grad
                print "image %4.1d   energy= %+e   |grad|= %e" % (i,en, la.norm(grad))
    def _getTangents(self):
        """tangents along the path at the image positions"""
        self.tangents = [None for Ri in self.R]
        for i in xrange(1,len(self.R)-1):
            if self.V[i-1] <= self.V[i] <= self.V[i+1]:
                self.tangents[i] = self.R[i+1] - self.R[i]
            elif self.V[i+1] < self.V[i] < self.V[i-1]:
                self.tangents[i] = self.R[i] - self.R[i-1]
            else:
                dVmax = max(abs(self.V[i+1] - self.V[i]),abs(self.V[i-1] - self.V[i]))
                dVmin = min(abs(self.V[i+1] - self.V[i]),abs(self.V[i-1] - self.V[i]))
                taup = self.R[i+1] - self.R[i]
                taum = self.R[i] - self.R[i-1]
                if self.V[i+1] > self.V[i-1]:
                    self.tangents[i] = taup*dVmax + taum*dVmin
                elif self.V[i+1] < self.V[i-1]:
                    self.tangents[i] = taup*dVmin + taum*dVmax
                else:
                    self.tangents[i] = self.R[i+1] - self.R[i-1] # ?
            # normalize tangents
            self.tangents[i] /= norm(self.tangents[i])
    def _getEffectiveForces(self):
        # effective total force
        self.effF = [None for Ri in self.R]
        for i in xrange(1,len(self.R)-1):
            # spring force parallel to tangents
            km = self.force_constant
            if self.states[i+1] != self.states[i]:
                kp = self.force_constant_surface_switch
                dR = self.R[i+1] - self.R[i]
                dE = self.V[i+1] - self.V[i]
                dF = self.F[i+1] - self.F[i]

                F1 = dR + (dE - np.dot(self.F[i+1], dR)) * self.F[i+1]
                F2   = -dR + (-dE + np.dot(self.F[i], dR)) * self.F[i]
                print "dE = %s" % dE
                print "erf(dE) = %s" % special.erf(dE)
                print "Fi+1 = %s" % self.F[i+1]
                print "Fi   = %s" % self.F[i]
                Fspring = kp * (F1 + F2)
                print "Fspring = %s" % Fspring
            else:
                kp = self.force_constant
                Fspring = kp * norm(self.R[i+1] - self.R[i]) * self.tangents[i] # new implementation by Henkelman/Jonsson
                                
            if self.states[i] != self.states[i-1]:
                km = self.force_constant_surface_switch
                Fspring -= dot(km*(self.R[i] - self.R[i-1]), self.tangents[i]) * self.tangents[i] # from original implementation of NEB
            else:
                km = self.force_constant
                Fspring -= km*norm(self.R[i] - self.R[i-1]) * self.tangents[i] # new implementation by Henkelman/Jonsson
            #Fspring = dot(self.force_constant*((self.R[i+1] - self.R[i]) - (self.R[i] - self.R[i-1])), self.tangents[i]) * self.tangents[i] # from original implementation of NEB
            # perpendicular component of true forces
            Fnudge = self.F[i] - dot(self.F[i],self.tangents[i])*self.tangents[i]
            self.effF[i] = Fspring + Fnudge
        if self.optimize_endpoints == True:
            # initial and final weights move toward minima
            self.effF[0] = self.F[0]
            self.effF[-1] = self.F[-1]
        else:
            # supress force on ends so that they stay put
            self.effF[0] = zeros(self.F[0].shape)
            self.effF[-1] = zeros(self.F[-1].shape)
    def _converged(self, tolerance):
        """Check if average forces have dropped below certain threshold"""
        self.avgForce = 0.0
        for i in xrange(1,len(self.R)-1):
            self.avgForce += norm(self.effF[i])
        if self.optimize_endpoints == True:
            # force on enpoints should only add to the convergence measure
            # is they can be optimized
            self.avgForce += norm(self.effF[0])
            self.avgForce += norm(self.effF[-1])
        self.avgForce /= len(self.R)
        print "average force = %2.5f (tolerance = %2.5f)" % (self.avgForce, tolerance)
        if self.avgForce < tolerance:
            return True
        else:
            return False
    def findMEP(self, tolerance=0.001, nsteps=1000, dt=0.01, friction=0.05, optimize_endpoints=True):
        """
        find minimum energy path by allowing the band to move with some friction to
        damp out oscillations. After the optimization the optimally distributed images
        can be retrieved with .getImages().

        Parameters:
        ===========
        tolerance: If the average force on the band drops below this value, the optimization is stopped
        nsteps: run damped dynamics for nsteps.
        dt: time step
        friction: damping coefficient between 0.0 (no damping) and 1.0 (do not use such high damping)
        optimize_endpoints: if True, end points of band move towards energy minima.
        """
        self.optimize_endpoints = optimize_endpoints
        Rlast = [Ri for Ri in self.R] # R(t-dt), R[0] and R[-1] stay always the same
        Rnext = [Ri for Ri in self.R] # R(t+dt)
        for self.istep in xrange(0, nsteps):
            self._getPES()
            self._getTangents()
            self._getEffectiveForces()
            # optimized positions of intermediate images
            # and minimize positions of ends
            for i in xrange(0, len(self.R)):
                if i in [0, len(self.R)-1] and (self.optimize_endpoints == False):
                    # as effF[0] = 0 and effF[-1] = 0 this line should not be neccessary ????
                    continue
                if self.istep == 0:
                    # Euler step, without initial velocity
                    Rnext[i] = self.R[i] + 0.5*self.effF[i]/self.mass*pow(dt,2)
                    Rlast[i] = self.R[i]
                    self.R[i] = Rnext[i]
                else:
                    # damped Verlet algorithm
                    Rnext[i] = (2.0-friction)*self.R[i] - (1.0-friction)*Rlast[i] + self.effF[i]/self.mass*pow(dt,2)
                    Rlast[i] = self.R[i]
                    self.R[i] = Rnext[i]
            if self._converged(tolerance):
                break
            self._writeIteration()
            self.plot()
        #
        else:
            raise Warning("Could not find minimum energy path in %s iterations (average force = %2.5f > tolerance = %2.5f)." % (self.istep+1, self.avgForce, tolerance))
    def _writeIteration(self):
        import sys
        print "Iteration = %s  " % self.istep
        sys.stdout.flush()
    def plot(self):
        images = self.getImages()
        energies = self.V
        if self.istep % self.print_every == 0:
            geometries = [XYZ.vector2atomlist(im, self.atomlist) for im in images]
            xyz_out = "neb_%s_%4.4d.xyz" % (self.name, self.istep)
            XYZ.write_xyz(xyz_out, geometries)
            print "wrote path for iteration %d to %s" % (self.istep, xyz_out)
            if energies != []:
                # first column: index of image
                # second column: energy of image
                data = np.vstack((np.arange(0, len(images)), energies)).transpose()
                np.savetxt("path_energies_%s_%4.4d.dat" % (self.name, self.istep), data)

    def getImages(self):
        return self.R
    def getImageStates(self):
        return self.states
    def splineMEProfile(self):
        """
        interpolate the energy along MEP between images with a cubic spline.
        
        Returns:
        ========
        me: callable function, that returns the energy as a function of the reaction coordinate
          which runs from 0 (educts) to 1 (product)
        """
        n = len(self.R)
        x = zeros(n)
        f = zeros(n)
        f1 = zeros(n) # first derivative of f
        for i in range(0,n):
            if i == 0:
                t = self.R[1] - self.R[0]
                x[i] = 0.0
            else:
                t = self.R[i] - self.R[i-1]
                x[i] = x[i-1] + norm(t)
            f[i] = self.V[i]
            f1[i] = dot(self.F[i], t/norm(t))
        def MEfunc(rxc):
            """
            potential energy along minimum energy path.

            Parameters:
            ===========
            rxc: reaction coordinate (between 0.0 and 1.0)
            """
            assert 0.0 <= rxc <= 1.0
            s = rxc*x[-1]
            ic = argmin(abs(x - s))
            if s < x[ic]:
                ic -= 1
            if s == x[ic]:
                return f[ic]
            dx = norm(x[ic+1]-x[ic])
            df = f[ic+1]-f[ic]
            a = (s-x[ic])/dx
            assert 0.0 <= a <= 1.0
            fa = (1-a)*f[ic] + a*f[ic+1] + a*(1-a)*((1-a)*(-f1[ic]*dx-df) + a*(+f1[ic+1]*dx + df))
            return fa
        return frompyfunc(MEfunc,1,1)

    def splineMEPath(self):
        """
        interpolate the minimum energy path with a cubic spline along the images.
        
        Returns:
        ========
        mep: callable function, that returns the geometry as a function of the reaction coordinate
          which runs from 0 (educts) to 1 (product)
        """
        n = len(self.R)
        x = zeros(n)
        images = self.getImages()
        gradients =  [-f for f in self.F]
        for i in range(0,n):
            if i == 0:
                t = self.R[1] - self.R[0]
                x[i] = 0.0
            else:
                t = self.R[i] - self.R[i-1]
                x[i] = x[i-1] + norm(t)
        def MEPfunc(rxc):
            """
            linearly interpolated geometries along the minimum energy path.

            Parameters:
            ===========
            rxc: reaction coordinate (between 0.0 and 1.0)
            """
            assert 0.0 <= rxc <= 1.0
            s = rxc*x[-1]
            ic = argmin(abs(x - s))
            if s < x[ic]:
                ic -= 1
            if s == x[ic]:
                return images[ic]
            dx = norm(x[ic+1]-x[ic])
            assert x[ic] <= s <= x[ic+1]
            a = (s-x[ic])/dx
            assert 0.0 <= a <= 1.0
            geom = (1-a)*images[ic] + a*images[ic+1]
            return geom
        return MEPfunc    


if __name__ == "__main__":
    import sys
    from scipy import optimize
    from os.path import basename, exists

    usage = """
       Usage: %s  path.xyz

    optimize a reaction path on the ground state using Gaussian 09.

    Input Files:
       path.xyz    -   xyz-file with educt, intermediates and product
       neb.gjf     -   Gaussian 09 input script driving the energy calculation (see below)

    Output Files:
       neb_####.xyz            -  current reaction path
       path_energies_####.dat  -  current energy profile

    The single argument should be an xyz-file containing initial guess
    geometries along the reaction path. This path will be optimized
    using the nudged elastic band (NEB) algorithm.

    In addition you have to set up a Gaussian input script called `neb.gjf` 
    that computes the gradient and saves it in a checkpoint file called 
    'grad.chk'. The geometry is updated via a file called `geom` that 
    is imported at the end of the script. 
    An example input script is given below:

    ------- example for neb.gjf ----------
    %%Chk=grad.chk
    %%Nproc=1
    %%Mem=1Gb
    # B3LYP/def2-SVP Force
      NoSymm SCF=QC
  
    s0 gradient

    0 3
    @geom


    --------------------------------------

    The NEB calculations are parallelized over the images. The number of images that are 
    processed at the same time are specified by the option `parallel_images`. 
    The calculation for each image can be run in parallel, as well. The %%Nproc=... line 
    in the Gaussian job file should agree with the value provided in the option `procs_per_image`.

    Every N time steps the current path and the energy profile are written
    to `neb_####.xyz` and `path_energies_####.dat` where #### is replaced by the
    name of the input xyz-file and the time step.

    To see all options for controlling the NEB calculation, call this script
    with the --help option.
    """ % basename(sys.argv[0])

    parser = optparse.OptionParser(usage)
    # options
    parser.add_option("-i", "--procs_per_image", dest="procs_per_image", type=int, default=1,
                      help="Number of processors used in the calculation for a single image [default: %default]")
    parser.add_option("-m", "--mem_per_image", dest="mem_per_image", type=str, default="6Gb",
                      help="Amount of memory to be allocated for each image calculation [default: %default]")
    parser.add_option("-p", "--parallel_images", dest="parallel_images", type=int, default=1,
                      help="How many images should be processed in parallel? Each image will be run with `procs_per_image` processors [default: %default]")
    parser.add_option("-c", "--force_constant", dest="force_constant", type=float, default=1.0,
                      help="Force constant for strings connecting the beads on the elastic band [default: %default]")
    parser.add_option("--mass",         dest="mass", type=float, default=1.0,
                      help="Mass of beads [default: %default]")
    parser.add_option("-t", "--tolerance", dest="tolerance", type=float, default=0.02,
                      help="The optimization is finished, if the average force on the band drops below this value [default: %default]")
    parser.add_option("-n", "--nsteps", dest="nsteps", type=int, default=1000,
                      help="Run damped dynamics for NSTEPS steps [default: %default]")
    parser.add_option("--dt",           dest="dt", type=float, default=0.1,
                      help="Time step for integrating damped dynamics [default: %default]")
    parser.add_option("-f", "--friction", dest="friction", type=float, default=0.2,
                      help="damping coefficient between 0.0 (no damping) and 1.0 (do not use such high damping) [default: %default]")
    parser.add_option("-e", "--optimize_endpoints", dest="optimize_endpoints", action="store_true", default="False",
                      help="Optimize the endpoints of the path as well [default: %default]")
    parser.add_option("-s", "--scratch_dir", dest="scratch_dir", type=str, default="/sscratch/$PBS_JOBID",
                      help="Path to scratch directory [default: %default]")
    parser.add_option("--print_every", dest="print_every", type=int, default=1,
                      help="Print current path and energies every N-th step [default: %default]")
    parser.add_option("--calculator", dest="calculator", type=str, default="g09",
                      help="Choose electronic structure program, 'g09' (Gaussian) or 'qchem'. If Qchem is chosen, an input file called 'neb.in' has to be present instead of 'neb.gjf' [default: %default]")
    
    (opts, args) = parser.parse_args()
    
    if len(args) < 1:
        print usage
        exit(-1)

    try:
        os.environ["PBS_JOBID"]
    except KeyError:
        raise KeyError("This script can only be run through a PBS or SLURM queue, environment variable PBS_JOBID not found!")

    if opts.calculator == "g09" and not exists("neb.gjf"):
        print "ERROR: Gaussian input script 'neb.gjf' not found in current folder!"
        exit(-1)

    if opts.calculator == "qchem" and not exists("neb.in"):
        print "ERROR: QChem input script 'neb.in' not found in current folder!"
        exit(-1)

    if opts.calculator == "bagel" and not exists("neb.json"):
        print "ERROR: BAGEL input script 'neb.json' not found in current folder!"
        exit(-1)
        
    print """
    ****************************
    *                          *
    *  Nudged Elastic Band     *
    *                          *
    ****************************
    """
    print opts
    
    # path to xyz-file
    xyz_file = args[0]
    # 
    name = basename(xyz_file.replace(".xyz", ""))
    # Read the geometry from the xyz-file
    atomlists = XYZ.read_xyz(xyz_file)
    atomlist = atomlists[0]

    neb = NEB(force_constant=opts.force_constant, mass=opts.mass,
              procs_per_image=opts.procs_per_image, parallel_images=opts.parallel_images,
              mem_per_image=opts.mem_per_image,
              scratch_dir=opts.scratch_dir,
              calculator=opts.calculator,
              print_every=opts.print_every)
    neb.setGeometry(atomlist)
    neb.setName(name)

    images = [XYZ.atomlist2vector(atomlist) for atomlist in atomlists]
    neb.setImages(images, states=[0 for im in images])
    neb.addImagesLinearly(2)
    # save initial path
    neb.plot()
    neb.findMEP(tolerance=opts.tolerance, nsteps=opts.nsteps,
                dt=opts.dt, friction=opts.friction, optimize_endpoints=opts.optimize_endpoints)

    me = neb.splineMEProfile()
    mep = neb.splineMEPath()
    
    
