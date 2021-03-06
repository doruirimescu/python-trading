# For investing api
pip install bs4
pip install lxml
pip install argparse

# For xtb api
git clone git@github.com:doruirimescu/XTBApi.git
cd XTBApi/
python3 -m venv env
. env/bin/activate
pip install .

# For candle
pip install pandas
pip install plotly

#For tests
pip3 install pytest

#Install talib
# wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
# tar -xzf ta-lib-0.4.0-src.tar.gz
# cd ta-lib/
# sudo ./configure
# sudo make
# sudo make install
# pip install ta-lib
# In /etc/ld.so.conf
# include /etc/ld.so.conf.d/*.conf
# include /home/doru/.local/lib
