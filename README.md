# python-1c-exchange-emulate

1C exchange emulator implements [protocol exchange 1C with 1C-Bitrix](http://v8.1c.ru/edi/edi_stnd/131/)

1. Prepare your 1C-exchange files
2. Place python script with exchange files
3. Set in script your 1C-Bitrix site host, exchange url, login and password
4. Run script: python exchange.py

OR use only command line
<pre><code>
  python exchange.py host url login password
        host           - Exchange host without http(s). For example: example.com
        url            - URL to exchange 1C-Bitrix component. For example: /catalog/exchange_1c.php
        login          - Exchange user login
        password       - Exchange user password
</code></pre>

OR use docker container
1. Create image
<pre><code>
docker build -t maksze/python-1c-exchange-emulate .
</code></pre>
2. Run in directory with files for exchange
<pre><code>
docker run -i -t -v $PWD:/opt/exchange-files maksze/python-1c-exchange-emulate example.com /catalog/exchange_1c.php login password
</code></pre>
