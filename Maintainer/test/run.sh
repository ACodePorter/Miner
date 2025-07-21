my_dir=$(realpath $(dirname $0))
cur_dur=$(pwd)
cd $my_dir

export PYTHONPATH="$my_dir/..:$PYTHONPATH"
export PYTHONPATH="$my_dir/../Detonator:$PYTHONPATH"
export PYTHONPATH="$my_dir/../DataMiner:$PYTHONPATH"
export PYTHONPATH="$my_dir/../MinerWorkers:$PYTHONPATH"

echo $PYTHONPATH

if [ "$#" -ne 0 ]; then
  python -m unittest -v "$@"
else
  python -m unittest discover -v -c
fi

cd "$cur_dur"
