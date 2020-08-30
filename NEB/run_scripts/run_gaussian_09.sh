#!/bin/bash
#
# To submit a Gaussian 09 input file `molecule.gjf` to 4 processors
# using 10Gb of memory run
#
#   run_gaussian.sh  molecule.gjf  4   10Gb
#
# To submit to a specifiy SLURM queue you can set the environment variable
# SBATCH_PARTITION before executing this script, e.g.
#
#   SBATCH_PARTITION=fux  run_gaussian_09.sh molecule.gjf 4 10Gb
#

show_help() {
    echo "Input script $1 does not exist!"
    echo " "
    echo "  Usage: $(basename $0)  molecule.gjf  nproc  mem"
    echo " "
    echo "    submits Gaussian script molecule.gjf for calculation with 'nproc' processors"
    echo "    and memory 'mem'. "
    echo " "
    echo "    The Gaussian log-file is written to molecule.out in the same folder,"
    echo "    whereas the checkpoint files are copied back from the node only after the calculation "
    echo "    has finished."
    echo " "
    echo "    In the Gaussian script '%Nproc=...' should be omitted, but the amount of memory still has"
    echo "    to be specified via '%Mem=...'' ."
    echo " "
    echo "  Example:  $(basename $0)  molecule.gjf 16  40Gb"
    echo " "
    exit 1
}

# Additional options for sbatch must precede all arguments
sbatch_options=""
option_fchk=""
while :; do
    case $1 in
	-h|--help)
	    show_help
	    ;;
	-w|--wait)
	    # Wait for the job to finish and return exit code 1 if the Gaussian
	    # calculation failed and 0 if it succeded.
	    echo "Script will hang until the job finishes."
	    sbatch_options="${sbatch_options} --wait"
	    shift
	    ;;
	-f|--fchk)
	    # Convert checkpoint files to fromatted files.
	    echo "Checkpoint files will be formatted."
	    option_fchk="yes"
	    shift
	    ;;
	--)
	    # end of options
	    shift
	    break
	    ;;
	*)
	    # default case
	    break
    esac
done

if [ ! -f "$1" ]
then
    show_help
fi

# input script
job=$(readlink -f $1)
# errors and output of submit script will be written to this file
err=$(dirname $job)/$(basename $job .gjf).err
# name of the job which is shown in the queueing table
name=$(basename $job .gjf)
# number of processors (defaults to 1)
nproc=${2:-1}
# memory (defaults to 6Gb)
mem=${3:-6Gb}
# directory where the input script resides, this were the output
# will be written to as well.
rundir=$(dirname $job)

# The submit script is sent directly to stdin of qsub. Note
# that all '$' signs have to be escaped ('\$') inside the HERE-document.

echo "submitting '$job' (using $nproc processors and $mem of memory)"

# submit to slurm queue
sbatch $sbatch_options <<EOF
#!/bin/bash

# for Slurm
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=${nproc}
#SBATCH --mem=${mem}
#SBATCH --job-name=${name}
#SBATCH --output=${err}

#NCPU=\$(wc -l < \$SLURM_JOB_NODELIST)
NNODES=\$(uniq \$SLURM_JOB_NODELIST | wc -l)
DATE=\$(date)
SERVER=\$SLURM_SUBMIT_HOST
SOURCEDIR=\${SLURM_SUBMIT_DIR}

echo ------------------------------------------------------
echo HOST: \$SLURM_SUBMIT_HOST
echo PARTITION: \$SLURM_JOB_PARTITION
echo HOME: \$HOME
echo PATH: \$PATH
echo JOBNAME: \$SLURM_JOB_NAME
echo JOBID: \$SLURM_JOB_ID
echo ARRAYID: \$SLURM_ARRAY_TASK_ID
echo WORKDIR: \$SLURM_SUBMIT_DIR
echo NODEFILE: \$SLURM_JOB_NODELIST
echo NUM_PPN: \$SLURM_JOB_CPUS_PER_NODE
echo ------------------------------------------------------
echo WORKDIR: \$WORKDIR
echo SOURCEDIR: \$SOURCEDIR
echo ------------------------------------------------------
echo "This job is allocated on '\${NCPU}' cpu(s) on \$NNODES"
echo "Job is running on node(s):"
cat \$SLURM_JOB_NODELIST

# Here required modules are loaded and environment variables are set
module load g09

# Input and log-file are not copied to the scratch directory.
in=${job}
out=\$(dirname \$in)/\$(basename \$in .gjf).out

# Calculations are performed in the user's scratch
# directory. For each job a directory is created
# whose contents are later moved back to the server.

tmpdir=/scratch
jobdir=\$tmpdir/\${SLURM_JOB_ID}

mkdir -p \$jobdir

# If the script receives the SIGTERM signal (because it is removed
# using the qdel command), the intermediate results are copied back.

function clean_up() {
    # remove temporary Gaussian files
    rm -f \$jobdir/Gau-*
    # move checkpoint files back
    mv \$jobdir/* $rundir/
    # delete temporary folder
    rm -f \$tmpdir/\${SLURM_JOB_ID}/*
}

trap clean_up SIGHUP SIGINT SIGTERM

# The Gaussian job might depend on old checkpoint files specified
# with the %OldChk=... option. These checkpoint files have to be
# copied to the scratch folder to make them available to the script.
for oldchk in \$(grep -i "%oldchk" \$in | sed 's/%oldchk=//gi')
do
   echo "job needs old checkpoint file '\$oldchk' => copy it to scratch folder"
   if [ -f \$oldchk ]
   then
      cp \$oldchk \$jobdir
   else
      echo "\$oldchk not found"
   fi
done

# Copy external @-files (geometries, basis sets) to the scratch folder
for atfile in \$(grep -i "^@" \$in | sed 's/@//gi')
do
   echo "job needs external file '\$atfile' => copy it to scratch folder"
   if [ -f \$atfile ]
   then
      cp \$atfile \$jobdir
   else
      echo "\$atfile not found"
   fi
done

# Go to the scratch folder and run the calculations. Checkpoint
# files are written to the scratch folder. The log-file is written
# directly to $out (in the global filesystem).

cd \$jobdir

echo "Calculation is performed in the scratch folder"
echo "   \$(hostname):\$jobdir"

echo "Running Gaussian ..."
g09 -p=${nproc} < \$in &> \$out

# Did the job finish successfully ?
success=\$(tail -n 1 \$out | grep "Normal termination of Gaussian")
if [ "\$success" ]
then
   echo "Gaussian job finished normally."
   ret=0
else
   echo "Gaussian job failed, see \$out."
   ret=1
fi

# create formatted checkpoint files
if [ "$option_fchk" ]
then
   echo "Formatting checkpoint files ..."
   for chk in *.chk
   do
      if [ -f "\$chk" ]
      then
          formchk \$chk 2>&1
      fi
   done
fi

# The results are copied back to the server
# and the scratch directory is cleaned.
echo "Copying results back ..."

clean_up

DATE=\$(date)
echo ------------------------------------------------------
echo End date: \$DATE
echo ------------------------------------------------------

# Pass return value of Gaussian job on to the SLURM queue, this allows
# to define conditional execution of dependent jobs based on the
# exit code of a previous job.
echo "exit code = \$ret"
exit \$ret

EOF

# Exit code of 'sbatch --wait ...' is the output of the batch script, i.e. $ret.
exit $?
