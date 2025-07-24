#!/bin/sh

# set -x
# Exit immediately if a command exits with a non-zero status.
set -e

MY_PWD=$PWD
MY_DIR=$(realpath $(dirname $0))

RELEASE_DIR=$MY_DIR/miner/release
BROWSERSCRAPER_RELEASE_DIR=$MY_DIR/browserscraper/release
MAINTAINER_RELEASE_DIR=$MY_DIR/maintainer/release
TRADER_RELEASE_DIR=$MY_DIR/trader/release

function cleanup() {
    # This function is called on exit to clean up temporary files.
    echo "Cleaning up temporary release directories..."
    rm -rf "$RELEASE_DIR"
    rm -rf "$BROWSERSCRAPER_RELEASE_DIR"
    rm -rf "$MAINTAINER_RELEASE_DIR"
    rm -rf "$TRADER_RELEASE_DIR"
    cd "$MY_PWD"
}

function exit_callback() {
    local exit_status=$?
    cleanup # Always run cleanup
    if [ $exit_status -eq 0 ]; then
        echo "✅ Deployment script finished successfully."
    else
        echo "❌ Deployment script failed with exit code: $exit_status."
    fi
    set +x
    set +e
    exit $exit_status
}

# Trap the EXIT signal to run the exit_callback function when the script finishes.
trap exit_callback EXIT

echo "Let's go ..."

usage() {
    echo "Usage: $0 <github_pat_token> <runtime_env[PROD|TEST|DEV]> [miner_data_dir]"
    exit 1
}
if [ -n "$1" ]; then
    export GITHUB_TOKEN=$1
else
    usage
    exit 1
fi



if [ -n "$2" ]; then
    export RUNTIME_ENV=$2
else
    usage
    exit 1
fi

mkdir -p $HOME/.miner/mongogo

export MINER_DATA=$HOME/.miner/data
if [ -n "$3" ];then
    export MINER_DATA=$2
fi

# Get git user name and email from host
export GIT_USER_NAME=$(git config --get user.name)
export GIT_USER_EMAIL=$(git config --get user.email)

echo "Github Token: $GITHUB_TOKEN"
echo "Runtime Env: $RUNTIME_ENV"
echo "Miner Data Dir: $MINER_DATA"
echo "Git user name: $GIT_USER_NAME"
echo "Git user email: $GIT_USER_EMAIL"

mkdir -p $MINER_DATA

export MONGO_INITDB_ROOT_USERNAME=root
export MONGO_INITDB_ROOT_PASSWORD=12qw
if [ -n "$3" ]; then
    export MONGO_INITDB_ROOT_USERNAME=$3
fi
if [ -n "$4" ]; then
    export MONGO_INITDB_ROOT_PASSWORD=$4
fi

cd $MY_DIR

mkdir -p "$MY_DIR/base/bin/"
wget -nv -c https://repo.anaconda.com/miniconda/Miniconda3-py312_24.11.1-0-Linux-x86_64.sh -O $MY_DIR/base/bin/Miniconda3.sh

rm -rf $RELEASE_DIR
mkdir -p $RELEASE_DIR

rm -rf $BROWSERSCRAPER_RELEASE_DIR
mkdir -p $BROWSERSCRAPER_RELEASE_DIR

rm -rf $MAINTAINER_RELEASE_DIR
mkdir -p $MAINTAINER_RELEASE_DIR

rm -rf $TRADER_RELEASE_DIR
mkdir -p $TRADER_RELEASE_DIR

cp -a $MY_DIR/../Detonator $RELEASE_DIR/
cp -a $MY_DIR/../DataMiner $RELEASE_DIR/
cp -a $MY_DIR/../MarketBreadth $RELEASE_DIR/
cp -a $MY_DIR/../MinerWorkers $RELEASE_DIR/
cp -a $MY_DIR/../MinerService $RELEASE_DIR/
cp -a $MY_DIR/../BrowserScraper $RELEASE_DIR/
cp -a $MY_DIR/../MinerService/run_service_as_prod_uds.sh $RELEASE_DIR/
cp -a $MY_DIR/miner/run_socks5_proxy.sh $RELEASE_DIR/
cp -a $MY_DIR/miner/docker_entry.sh $RELEASE_DIR/

cp -a $MY_DIR/../Detonator $BROWSERSCRAPER_RELEASE_DIR/
cp -a $MY_DIR/../DataMiner $BROWSERSCRAPER_RELEASE_DIR/
cp -a $MY_DIR/../MinerWorkers $BROWSERSCRAPER_RELEASE_DIR/
cp -a $MY_DIR/../BrowserScraper $BROWSERSCRAPER_RELEASE_DIR/
cp -a $MY_DIR/browserscraper/docker_entry.sh $BROWSERSCRAPER_RELEASE_DIR/

cp -a $MY_DIR/../Detonator $MAINTAINER_RELEASE_DIR/
cp -a $MY_DIR/../MarketBreadth $MAINTAINER_RELEASE_DIR/
cp -a $MY_DIR/../DataMiner $MAINTAINER_RELEASE_DIR/
cp -a $MY_DIR/../MinerWorkers $MAINTAINER_RELEASE_DIR/
cp -a $MY_DIR/../Maintainer $MAINTAINER_RELEASE_DIR/
cp -a $MY_DIR/maintainer/docker_entry.sh $MAINTAINER_RELEASE_DIR/

cp -a $MY_DIR/trader/docker_entry.sh $TRADER_RELEASE_DIR/

# Set base image folder
BASE_DIR=$MY_DIR/base
BASE_DOCKERFILE=$BASE_DIR/Dockerfile.base
BASE_IMAGE_TAG=miner-base:latest
BASE_HASH_FILE=$BASE_DIR/.docker_base_hash

if [ -f "$BASE_DOCKERFILE" ]; then
    # Compute hash of Dockerfile.base and any files it depends on (e.g., .condarc, Miniconda3.sh)
    BASE_HASH=$(cat "$BASE_DOCKERFILE" "$MY_DIR/base/bin/Miniconda3.sh" "$MY_DIR/base/requirements.txt" 2>/dev/null | sha256sum | awk '{print $1}')
    PREV_HASH=""
    if [ -f "$BASE_HASH_FILE" ]; then
        PREV_HASH=$(cat "$BASE_HASH_FILE")
    fi
    IMAGE_EXISTS=$(docker images -q $BASE_IMAGE_TAG)
    if [ -z "$IMAGE_EXISTS" ] || [ "$BASE_HASH" != "$PREV_HASH" ]; then
        echo "Building $BASE_IMAGE_TAG from $BASE_DOCKERFILE ..."
        docker build -f "$BASE_DOCKERFILE" -t $BASE_IMAGE_TAG "$BASE_DIR"
        echo "$BASE_HASH" > "$BASE_HASH_FILE"
    else
        echo "$BASE_IMAGE_TAG is up to date, skipping rebuild."
    fi
    # Create a dummy container to protect the base image from prune
    docker rm keep-miner-base || true
    docker create --name keep-miner-base $BASE_IMAGE_TAG || true
else
    echo "Dockerfile.base not found, skipping build."
    exit 1
fi

COMPOSE_BAKE=true docker compose --project-name miner up --build -d

#set +x
# The 'set +e' and final cleanup call are no longer needed as the EXIT trap handles the script's conclusion.
