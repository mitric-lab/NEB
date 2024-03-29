# NEB
Optimize a reaction path using the nudged elastic band algorithm. An electronic structure
method implemented in Gaussian 09/16, Q-Chem or BAGEL is used to calculate the energy and forces.
The optimization itself is driven by the BFGS algorithm.

Nudged elastic band (NEB) method for finding minimum energy paths (MEP) and saddle points.
Implementation based on
     "Improved tangent estimate in the nudged elastic band method for finding minimum energy paths and saddle points" by Henkelman, G.; Jonsson, H. J.Chem.Phys. 113, 9978 (2000)"

Requirements
----
Python 2.7+ or 3.5+ 
##### Python Packages
 -     numpy, argparse, future

Installation
----
Download the NEB directory<br>
```bash
git clone https://github.com/mitric-lab/NEB.git
```
Go into this new directory and install the Python package
```bash
cd NEB
python setup.py install
```
Now it should be possible to call the NEB program:
```bash
optmize_neb --help
```
The execution of the NEB program is only possible within the SLURM environment. The idea is that 
a SLURM job will execute the optimize_neb script and this job will automatically submit the force 
calculations of the individual images (geometries). 
Therefore, this NEB package contains submission scripts to send Gaussian/Q-Chem/Bagel jobs to the SLURM queue. 
It might be necessary to adopt them to your system. They are located in 
   ```NEB/run_scripts/```
Additionally, it is important that this path is included in your `$PATH` environment variable. In bash
you can execute something like this:
````
export PATH=__PATH_TO_YOUR_NEB_DIRECTORY__/NEB/run_scripts/:$PATH
```` 
    


Usage
----

 The NEB calculations are parallelized over the images. The number of images that are
 processed at the same time are specified by the option `parallel_images`.
 The calculation for each image can be run in parallel, as well. The `%Nproc=...` line
 in the Gaussian job file should agree with the value provided in the option `procs_per_image`.

 Every N time steps the current path and the energy profile are written
 to `neb_####.xyz` and `path_energies_####.dat` where #### is replaced by the
 name of the input xyz-file and the time step.

 To see all options for controlling the NEB calculation, call `optimize_neb`
 with the `--help` option.


-------------------
##### Input Files:<br/>
    path.xyz      -  xyz-file with educt, intermediates and product
    for Gaussian 09/16
      neb.gjf     -  Gaussian 09/16 input script driving the energy calculation (see below)
    for Q-Chem
      neb.in      -  Q-Chem input script driving the energy calculation (see below)

##### Output Files:<br/>
    neb_####.xyz            -  current reaction path
    path_energies_####.dat  -  current energy profile

---------------

The program expects the initial (unoptimised) paths (xyz file) as a single argument, e.g:
```
optimize_neb path.xyz
```
This single argument should be an xyz-file containing initial guess
geometries along the reaction path. This path will be optimized
using the nudged elastic band (NEB) algorithm.

#### Initial Path
The initial path for the NEB should be interpolated between the two minimum structures. There are two different 
algorithms that can be used. Either a linear interpolation (in internal coordinates), which is a for example a part
of the DFTBaby package by A. Humeniuk (see `interpolate_linearly.py` in DFTBaby). The more sophisticated way is to use 
the geodesic interpolation algorithm developed by T. Martinez and coworkers (see [Ref.](https://aip.scitation.org/doi/full/10.1063/1.5090303)).
Their algorithm is implemented in a python package and can be obtained from their [Github repository](https://github.com/virtualzx-nad/geodesic-interpolate).
A number of 12 to 16 interpolated structures is often a good choice. 


#### Interface to Gaussian 09/16
In addition you have to set up a Gaussian input script called `neb.gjf`
 that computes the gradient and saves it in a checkpoint file called
 'grad.chk'. The geometry is updated via a file called `geom` that
 is imported at the end of the script.
 An example `neb.gjf` is given below:
 ```
  ------- example for neb.gjf ----------
  %Chk=grad.chk                         !<-- Do not change this filename
  %Nproc=1                              !<-- This should be the same number as the --procs_per_image keyword
  %Mem=1Gb                              !<-- This number be 20-30% lower than the --mem_per_image keyword
  # B3LYP/def2SVP Force
    NoSymm

  s0 gradient

  0 1
  @geom                                 !<-- Do not change this filename

                                        !<-- Don't forget the extra line at the end 
  --------------------------------------
 ```

#### Interface to Q-Chem 
To use the NEB package in combination with Q-Chem you have to prepare a Q-Chem input
script called `neb.in`. Within this input file it is important that you request a force calculation
and that a Checkpoint file will be written. An example input script is shown below:
```
$comment
  Q-Chem input file
 1. A line prefixed with an exclamation mark ‘!’ is treated as a comment and will be ignored by the program
 2. Variables are case-insensitive (as is the whole Q-CHEM input file).
$end

$molecule
 0 1       ! Charge | Multiplicity | You do not have to specify the molecule here!
$end

$rem
 !--GENERAL Q-CHEM SETTINGS -----------------------------------------------------------------------
  MEM_TOTAL                 12250      ! maximum amount of ram memory (MB)
  MEM_STATIC                2000       ! static memory used (MB).
  AO2MO_DISK                50000      ! specifies maximum amount of memory written to scratch files (MB)
  GUI                       2          ! 0: generate no checkpoint file | 2: generate fchk
 !-------------------------------------------------------------------------------------------------

 !--SCF PROCEDURE ---------------------------------------------------------------------------------
  SCF_ALGORITHM             DIIS       ! DIIS |DM | GDM | RCA | ROOTHAN | DIIS_GDM | DIIS_DM | RCA_DIIS
  SCF_CONVERGENCE           8          ! SCF is converged when energy change is below 1e-X hartree
  SCF_MAX_CYCLES            150        ! controls the maximum number of scf iterations perimetted
  SYMMETRY_IGNORE           true       ! control whether to use symmetry and reorienation of the molecule
 !-------------------------------------------------------------------------------------------------

 !--SPECIFICATION OF JOBTYPE ----------------------------------------------------------------------
  JOBTYPE                   force       ! requests the computation of gradients
 !-------------------------------------------------------------------------------------------------

 !--LEVEL OF THEORY -------------------------------------------------------------------------------
  METHOD                    B3lYP       ! specifies the (TD)-DFT functional
  BASIS                     def2-svp    ! specifies basis set to be used
 !-------------------------------------------------------------------------------------------------
 $end
```


#### Visualization of results
After successful minimization of the reaction pathn you can plot the energy of the path during each iteration. Within the 
directory where the `neb_####.xyz` and `path_energies_####.dat` files are located, you can just call:
```
optimize_neb plot
```
This will open a Matplotlib window where you can slide through the iterations as shown below:<br>
<img src="http://jhoche.de/test.gif">


### Examples

Some examples with a submit script can be found in the NEB/examples directory.
- `water_flip_g16`: Reaction path of water flip with Gaussian16 in the singlet ground state at the DFT level.
- `water_flip_g16_excited_state`: Reaction path of water flip with Gaussian16 in the first singlet excited state at the DFT level.
- `water_flip_qchem`: Reaction path of water flip with Q-Chem in the singlet ground state at the DFT level.<br>
<br>
Make sure that the `optimize_neb` script
is within your `$PATH` variable, so that it can be called from the command-line. The NEB computations can be performed in the
  electronic ground state as well as in the excited state. The interfaces allow these features at least for Gaussian 16 and Q-Chem. Optimization
  within the frame of spin-polarised/unrestricted wave functions are also possible and tested with Gaussian 16 and Q-Chem. 

--------------
Optional arguments:
* `-h`,`--help`            show this help message and exit
* `-i PROCS_PER_IMAGE`, `--procs_per_image=PROCS_PER_IMAGE`
                     Number of processors used in the calculation for a
                     single image [default: 1]
* `-m MEM_PER_IMAGE`, `--mem_per_image=MEM_PER_IMAGE`
                     Amount of memory to be allocated for each image
                     calculation [default: 6Gb]
* `-p PARALLEL_IMAGES`, `--parallel_images=PARALLEL_IMAGES`
                     How many images should be processed in parallel? Each
                     image will be run with `procs_per_image` processors
                     [default: 1]
* `-c FORCE_CONSTANT`, `--force_constant=FORCE_CONSTANT`
                     Force constant for strings connecting the beads on the
                     elastic band [default: 0.1]
* `--mass=MASS`           Mass of beads [default: 1.0]
* `-t TOLERANCE`, `--tolerance=TOLERANCE`
                     The optimization is finished, if the maximum force on
                     the band drops below this value [default: 0.02]
* `-n NSTEPS`, `--nsteps=NSTEPS`
                     Run damped dynamics for NSTEPS steps [default: 1000]
* `--dt=DT`               Time step for integrating damped dynamics [default:
                     0.1]
* `-f FRICTION`, `--friction=FRICTION`
                     damping coefficient between 0.0 (no damping) and 1.0
                     (do not use such high damping) [default: 0.2]
* `-e`, `--optimize_endpoints`
                     Optimize the endpoints of the path as well [default: not set]
* `-s SCRATCH_DIR`, `--scratch_dir=SCRATCH_DIR`
                     Path to scratch directory [default:
                     /sscratch/$PBS_JOBID]
* `--print_every=PRINT_EVERY`
                     Print current path and energies every N-th step
                     [default: 1]
* `--integrator=INTEGRATOR`
                      Choose the integration algorithm for the optimization steps.
                      Use either 'verlet' or 'bfgs' (default). BFGS is strongly recommended.

* `--maxstep=MAXSTEP`
                      Maximum step length for BFGS optimization in Angstrom
                      [default: 0.01]

* `--calculator=CALCULATOR`
                     Choose electronic structure program, 'g09' or 'g16'
                     (Gaussian) or 'qchem'. If Q-Chem is chosen, an input
                     file called 'neb.in' has to be present instead of
                     'neb.gjf' [default: g16]
