#!/bin/bash

cwd=$(pwd)
cd /media/mihai/BTC/bitcoin-28.0/bin

./bitcoind -daemon

while true; do
  progress=$(./bitcoin-cli getblockchaininfo | jq .initialblockdownload)
  if [ "$progress" = "false" ]; then
    ./bitcoin-cli stop
    break
  fi
  sleep 60
done

cd "$cwd"
