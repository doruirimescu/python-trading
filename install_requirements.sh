cd deps/
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=/usr
make
make install
cd ../../

pip install -r Trading/requirements.txt

# For xtb api
git clone git@github.com:doruirimescu/XTBApi.git
cd XTBApi/
python3 -m venv env
. env/bin/activate
pip install .
