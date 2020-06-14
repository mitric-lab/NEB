#!/bin/bash
#
# Run a command string via the PBS or Slurm queue, for example
#
#   run_gamess.sh  "ls -l | wc -l"  4   10Gb
#

if [ $# == 0 ]
then
    echo " "
    echo "  Usage: $0  command  nproc  mem"
    echo " "
    echo "    submits a command (enclosed in quotation marks) to the queue with 'nproc' processors"
    echo "    and memory 'mem'. "
    echo " "
    echo "    A filename for the output is constructed from the command string by replacing special"
    echo "    characters with underscores. The output is written directly to the network filesystem"
    echo "    in the current working directoy."
    echo " "
    echo "  Example:  $(basename $0)  'ls -l | wc -l; sleep 10'  2  2Gb"
    echo " "
    echo "    The output is written to   ls_-l___wc_-l__sleep_10.out  in the current folder."
    echo " "
    exit 
fi

cmd=$1
# Create a UNIX filename from the command
name="${cmd//[^[:alnum:]._-]/_}"
# errors and output of submit script will be written to this file
out=$(pwd)/${name}.out
# number of processors (defaults to 1)
nproc=${2:-1}
# memory (defaults to 6Gb)
mem=${3:-6Gb}

# The submit script is sent directly to stdin of qsub. Note
# that all '$' signs have to be escaped ('\$') inside the HERE-document.

# submit to PBS queue
#qsub <<EOF
# submit to slurm queue
sbatch <<EOF
#!/bin/bash

# for Torque
#PBS -q batch
#PBS -l nodes=1:ppn=${nproc},vmem=${mem},mem=${mem}
#PBS -N ${name}
#PBS -jeo 
#PBS -e ${out} 

# for Slurm
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=${nproc}
#SBATCH --mem=${mem}
#SBATCH --job-name=${name}
#SBATCH --output=${out}

#NCPU=\$(wc -l < \$PBS_NODEFILE)
NNODES=\$(uniq \$PBS_NODEFILE | wc -l)
DATE=\$(date)
SERVER=\$PBS_O_HOST
SOURCEDIR=\${PBS_O_WORKDIR}

echo ------------------------------------------------------
echo PBS_O_HOST: \$PBS_O_HOST
echo PBS_O_QUEUE: \$PBS_O_QUEUE
echo PBS_QUEUE: \$PBS_O_QUEUE
echo PBS_ENVIRONMENT: \$PBS_ENVIRONMENT
echo PBS_O_HOME: \$PBS_O_HOME
echo PBS_O_PATH: \$PBS_O_PATH
echo PBS_JOBNAME: \$PBS_JOBNAME
echo PBS_JOBID: \$PBS_JOBID
echo PBS_ARRAYID: \$PBS_ARRAYID
echo PBS_O_WORKDIR: \$PBS_O_WORKDIR
echo PBS_NODEFILE: \$PBS_NODEFILE
echo PBS_NUM_PPN: \$PBS_NUM_PPN
echo ------------------------------------------------------
echo WORKDIR: \$WORKDIR
echo SOURCEDIR: \$SOURCEDIR
echo HOSTNAME: \$(hostname)
echo ------------------------------------------------------
echo "This job is allocated on '\${NCPU}' cpu(s) on \$NNODES"
echo "Job is running on node(s):"
cat \$PBS_NODEFILE
echo ------------------------------------------------------
echo Start date: \$DATE
echo ------------------------------------------------------

# Here required modules are loaded and environment variables are set
module load dftbaby

cd \$PBS_O_WORKDIR

echo "Running command '$cmd'"
echo "   ##### START #####"
$cmd
echo "   ##### FINISH ####"

DATE=\$(date)
echo ------------------------------------------------------
echo End date: \$DATE
echo ------------------------------------------------------

EOF

echo "Submitting command '$cmd' (using $nproc processors and $mem of memory)"
echo "Output will be written to '$out'."
