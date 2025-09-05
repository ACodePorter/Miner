my_dir=$(realpath "$(dirname $0)")
cur_dur=$(pwd)
cd $my_dir || exit 1

export PYTHONPATH="$my_dir/..:$my_dir/../Detonator:$my_dir/../DataMiner/:$PYTHONPATH"


if [ "$#" -ne 0 ]; then
  python -m unittest -v "$@"
else
  python -m unittest discover -v -c
fi

cd "$cur_dur" || exit 1
