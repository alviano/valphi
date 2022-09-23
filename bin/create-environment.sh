#!/bin/sh

echo "Specify the environment name, or type ENTER to use valphi"
read name
if [ -z "$name" ]; then
    name="valphi"
fi

conda create --name "$name" python=3.10

conda install --yes --name "$name" pytest
conda install --yes --name "$name" -c potassco clingo
conda install --yes --name "$name" -c conda-forge typeguard
conda install --yes --name "$name" -c conda-forge rich
conda install --yes --name "$name" -c conda-forge typer