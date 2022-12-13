#!/bin/sh

echo "Specify the environment name, or type ENTER to use valphi"
read name
if [ -z "$name" ]; then
    name="valphi"
fi

conda create --name "$name" python=3.10 --yes

conda install --yes --name "$name" -c conda-forge poetry
conda install --yes --name "$name" -c conda-forge chardet
conda install --yes --name "$name" -c potassco clingo
conda update --all --yes --name "$name"

echo "Activate the environment (conda activate $name) and run \"poetry install\""
