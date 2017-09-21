# -*- coding: utf-8 -*-
import base64
import contextlib
import datetime
import os
import string
import time
import urllib
from re import findall
import sys
from sys import exit as die
from sys import stderr
from zipfile import ZipFile, ZIP_DEFLATED

try:
    import requests
except ImportError:
    die('В системе не установлен модуль requests\nДля установки выполните команду\npip install requests')

try:
    from termcolor import colored
except ImportError:
    die('В системе не установлен модуль termcolor\nДля установки выполните команду\npip install termcolor')


class UploadInChunks(object):
    def __init__(self, filename, chunksize=1 << 13):
        self.filename = filename
        self.chunksize = chunksize
        self.totalsize = os.path.getsize(filename)
        self.readsofar = 0

    def __iter__(self):
        with open(self.filename, 'rb') as _file:
            while True:
                data = _file.read(self.chunksize)
                if not data:
                    stderr.write("\n")
                    break
                self.readsofar += len(data)
                percent = self.readsofar * 1e2 / self.totalsize
                stderr.write("\r{percent:3.0f}%".format(percent=percent))
                yield data

    def __len__(self):
        return self.totalsize


class IterableToFileAdapter(object):
    def __init__(self, iterable):
        self.iterator = iter(iterable)
        self.length = len(iterable)

    def read(self, size=-1):
        # type: (object, int) -> object
        return next(self.iterator, b'')

    def __len__(self):
        return self.length


def step1(_exchange_url, _exchange_path, _login, _password):
    # type: (string, string, string, string, string) -> string
    print colored('Шаг #1: Авторизация', 'blue')

    params = urllib.urlencode({'type': 'catalog', 'mode': 'checkauth'})
    url = 'http://' + _exchange_url + _exchange_path + '?' + params
    auth = 'Basic ' + string.strip(base64.encodestring(_login + ':' + _password))

    r = requests.get(url, headers={'Authorization': auth}).text
    print r + '\n'

    temp = r.split('\n')

    if temp[0] != 'success':
        print colored('Авторизация провалена\nОбмен завершен ' + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                      'blue')
        die('Авторизация провалена\nОбмен завершен')
    else:
        print 'Авторизация выполнена успешно\n'

    # Идентификатор сессии
    return temp[2]


def step2(_exchange_url, _exchange_path, _session_id):
    # type: (string, string) -> dict
    print colored('Шаг #2: Инициализация', 'blue')

    params = urllib.urlencode({'type': 'catalog', 'mode': 'init'})
    url = 'http://' + _exchange_url + _exchange_path + '?' + params

    result = requests.get(url, headers={'Cookie': 'PHPSESSID=' + _session_id}).text
    print result + '\n'

    # выбираем полученные парметры
    temp = findall(r"[\w]+", result)
    # проверка что параметры получены
    if temp[0] != 'zip' and temp[2] != 'file_limit':
        die('Ошибка инициализации\nОбмен завершен')
    else:
        print 'Инициализация выполнена успешно\n'
    # Сохранение полученных параметров
    return dict(zip=temp[1], file_limit=temp[3])


def step3(_exchange_url, _exchange_path, _session_id, _file_for_upload):
    # type: (string, string, string, string) -> bool
    print colored('Шаг #3: Загрузка файлов', 'blue')
    print 'Загрузка файла ' + _file_for_upload
    params = urllib.urlencode({'type': 'catalog', 'mode': 'file', 'filename': _file_for_upload})
    url = 'http://' + _exchange_url + _exchange_path + '?' + params
    it = UploadInChunks(_file_for_upload, 10)
    r = requests.post(url, data=IterableToFileAdapter(it), headers={'Cookie': 'PHPSESSID=' + _session_id})
    print r.text
    return True


def step4(_exchange_url, _exchange_path, _session_id, _file_for_import):
    # type: (string, string, string, string) -> bool
    print colored('Шаг #4: Импорт', 'blue')
    print 'Импорт ' + _file_for_import + '\n'
    r = 'progress'
    count = 1
    while 'progress' in r:
        params = urllib.urlencode({'type': 'catalog', 'mode': 'import', 'filename': _file_for_import})
        url = 'http://' + _exchange_url + _exchange_path + '?' + params
        r = requests.post(url, headers={'Cookie': 'PHPSESSID=' + _session_id}).text
        print colored('#' + count.__str__(), 'red'), r + '\n'
        count += 1
    return True


def zip_dir(base_dir, archive_name):
    assert os.path.isdir(base_dir)
    with contextlib.closing(ZipFile(archive_name + '.zip', "w", ZIP_DEFLATED)) as z:
        z.write(archive_name + '.xml')
        for root, dirs, files in os.walk(base_dir):
            if archive_name not in dirs and archive_name not in root:
                continue
            # NOTE: ignore empty directories
            for fn in files:
                if root == base_dir and archive_name not in fn:  # из корневой директории берем только с заданным именем
                    continue
                if root == base_dir and '.zip' in fn:  # исключаем из архивации все архивы
                    continue
                absfn = os.path.join(root, fn)
                zfn = absfn[len(base_dir) + len(os.sep):]  # XXX: relative path
                z.write(absfn, zfn)


def make_zip(_file):
    # type: (string) -> bool
    zf = ZipFile(_file + '.zip', mode='w')
    try:
        zf.write(_file + '.xml', compress_type=ZIP_DEFLATED)
    except RuntimeError:
        die('Ошибка архивации файлов [' + _file + '] при подготовке файлов к обмену')
    finally:
        zf.close()
    return True


def is_exists_directories_with_files_for_upload():
    files = get_files_from_work_directory()
    _files_for_send = []
    # выбрать названия всех файлов для обмена
    for exchange_file in files:
        if '.xml' in exchange_file:
            _files_for_send.append(exchange_file.replace('.xml', ''))

    exchange_directories = []

    for names in _files_for_send:
        for exchange_file in files:
            if exchange_file == names:
                exchange_directories.append(names)

    return len(exchange_directories) > 0


def get_exchange_files():
    files = get_files_from_work_directory()
    _files_for_send = []
    # выбрать названия всех файлов для обмена
    for exchange_file in files:
        if '.xml' in exchange_file:
            _files_for_send.append(exchange_file.replace('.xml', ''))

    exchange_directories = []

    for names in _files_for_send:
        for exchange_file in files:
            if exchange_file == '' + names + '_files':
                exchange_directories.append(names)

    # архивировать папки
    for name in exchange_directories:
        zip_dir(os.getcwd(), name)

    # архивировать файлы
    for name in _files_for_send:
        if name not in exchange_directories:
            make_zip(name)

    return _files_for_send


def get_files_from_work_directory():
    path = os.getcwd()
    files = os.listdir(path)
    return files


def make_import(_exchange_url, _exchange_path, _login, _password):
    try:
        start_time = time.time()
        print colored('Запущен обмен ' + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + '\n', 'blue')
        print 'Точка обмена: ' + colored(exchange_url + exchange_path, 'blue') + '\n'
        print 'Логин: ' + colored(login, 'blue') + '\n\nПароль: ' + colored(password, 'blue') + '\n'
        print 'Рабочая директория: ', colored(os.getcwd(), 'blue') + '\n'

        files_for_send = get_exchange_files()
        print 'Обнаруженные файлы для импорта: ', colored(files_for_send, 'blue'), '\n'

        for file_for_upload in files_for_send:
            exchange_begin_time = time.time()
            print colored('Начало импорта [' + file_for_upload + ']', 'green')
            session_id = step1(_exchange_url, _exchange_path, _login, _password)
            res = step2(_exchange_url, _exchange_path, session_id)

            if is_exists_directories_with_files_for_upload() and res['zip'] != 'yes':
                die('Присутствуют папки с файлами, их можно загрузить только архивом.\nПроверьте настройки компонента')

            if res['zip'] == 'yes':
                file_for_upload += '.zip'
            else:
                file_for_upload += '.xml'

            step3(_exchange_url, _exchange_path, session_id, file_for_upload)
            step4(_exchange_url, _exchange_path, session_id, file_for_upload.replace('.zip', '.xml'))
            print colored(
                'Конец импорта.\n' + ("Время выполнения - %s секунд(ы)\n" % (time.time() - exchange_begin_time)),
                'green')
        print colored('Обмен завершен ' + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + '\n' + (
            "Время выполнения - %s секунд(ы)\n" % (time.time() - start_time)), 'blue')

        return True

    except requests.exceptions.ConnectionError:
        print colored('Ошибка подключения к точке обмена. Проверьте параметры подключения.\nОбмен прерван', 'red')

        return False


exchange_url = ''
exchange_path = ''
login = ''
password = ''

# если в скрипт переданы параметры, работаем с ними
if len(sys.argv) > 1:
    try:
        # Сайт на который выполняется выгрузка
        exchange_url = sys.argv[1]
    except IndexError:
        print colored('Не задан хост обмена', 'red')
        die()

    try:
        # Точка обмена
        exchange_path = sys.argv[2]
    except IndexError:
        print colored('Не задана URL обмена', 'red')
        die()

    try:
        # Логин
        login = sys.argv[3]
    except IndexError:
        print colored('Не задан логин', 'red')
        die()

    try:
        # Пароль
        password = sys.argv[4]
    except IndexError:
        print colored('Не задан пароль', 'red')
        die()

# если параметры не переданы ине установлены в скрипте, выводим информацию по испольованию
elif exchange_url == '' and exchange_path == '' and login == '' and password == '':
    print 'python ' + __file__ + colored(' <host> <url> <login> <password>', 'blue')
    print colored('\t<host>\t\t', 'blue') + ' - Exchange host without http(s). For example: example.com'
    print colored('\t<url>\t\t',
                  'blue') + ' - URL to exchange 1C-Bitrix component. For example: /catalog/exchange_1c.php'
    print colored('\t<login>\t\t', 'blue') + ' - Exchange user login'
    print colored('\t<password>\t', 'blue') + ' - Exchange user password'
    die()

# Запустить обмен
make_import(exchange_url, exchange_path, login, password)