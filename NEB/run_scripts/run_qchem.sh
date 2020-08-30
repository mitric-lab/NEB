#!/bin/bash
#
# To submit a Q-Chem input file `water.in` to 4 processors
# using 10Gb of memory run
#
#   run_qchem.sh  water.in  4   10Gb
#
# To submit to a specifiy SLURM queue you can set the environment variable
# SBATCH_PARTITION before executing this script, e.g.
#
#   SBATCH_PARTITION=fux  run_qchem.sh molecule.gjf 4 10Gb
#

show_help() {
    echo "Input script $1 does not exist!"
    echo " "
    echo "  Usage: $(basename $0)  qchem.in  nproc  mem"
    echo " "
    echo "    submits Q-Chem script qchem.in for calculation with 'nproc' processors"
    echo "    and memory 'mem'. "
    echo " "
    echo "  Example:  $(basename $0)  qchem.in 16  40Gb"
    echo " "
    exit 1
}

# Additional options for sbatch must precede all arguments
sbatch_options=""
while :; do
    case $1 in
	-h|--help)
	    show_help
	    ;;
	-w|--wait)
	    # Wait for the job to finish and return exit code 1 if the
	    # calculation failed and 0 if it succeded.
	    echo "Script will hang until the job finishes."
	    sbatch_options="${sbatch_options} --wait"
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
err=$(dirname $job)/$(basename $job .in).err
# name of the job which is shown in the queueing table
name=$(basename $job .in)
# number of processors (defaults to 1)
nproc=${2:-1}
# memory (defaults to 6Gb)
mem=${3:-6Gb}
# directory where the input script resides, this were the output
# will be written to as well.
rundir=$(dirname $job)

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
echo ------------------------------------------------------
echo Start date: \$DATE
echo ------------------------------------------------------

# In case module command is not available
source /etc/profile.d/modules.sh

module load chem/qchem

jobdir=/scratch/\${SLURM_JOB_ID}
# scratch folder on compute node
export QCSCRATCH=\${jobdir}
export QCLOCALSCR=\${jobdir}

mkdir -p \$jobdir

# If the script receives the SIGTERM signal (because it is removed
# using the qdel command), the intermediate results are copied back.

function clean_up() {
    # move checkpoint files back
    mv \$jobdir/* $rundir/
    # delete temporary folder
    rm -f /scratch/\${SLURM_JOB_ID}/*
}

trap clean_up SIGHUP SIGINT SIGTERM

in=$job
out=\$(dirname \$in)/\$(basename \$in .in).out

# The QChem job might depend on other files specified with READ keyword.
# These files have to be copied to the scratch folder to make them
# available to the script.
for f in \$(grep -i "READ" \$in | sed 's/READ//gi')
do
   echo "job needs file '\$f' => copy it to scratch folder"
   if [ -f \$f ]
   then
      cp \$f \$jobdir
   else
      echo "\$f not found"
   fi
done

# Go to the scratch folder and run the calculations. Checkpoint
# files are written to the scratch folder. The log-file is written
# directly to \$out (in the global filesystem).

cd \$jobdir

echo "Running QChem ..."
qchem -nt ${nproc} \$in \$out > qchem_env_settings

# Did the job finish successfully ?
success=\$(tail -n 20 \$out | grep "Thank you very much for using Q-Chem.")
if [ "\$success" ]
then
   echo "QChem job finished normally."
   ret=0
else
   echo "QChem job failed, see \$out."
   ret=1
fi

# The results are copied back to the server
# and the scratch directory is cleaned.
echo "Copying results back ..."

clean_up

DATE=\$(date)
echo ------------------------------------------------------
echo End date: \$DATE
echo ------------------------------------------------------

# Pass return value of QChem job on to the SLURM queue, this allows
# to define conditional execution of dependent jobs based on the
# exit code of a previous job.
echo "exit code = \$ret"
exit \$ret

EOF

# Exit code of 'sbatch --wait ...' is the output of the batch script, i.e. $ret.
exit $?
