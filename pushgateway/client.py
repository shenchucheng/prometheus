#!/usr/bin/env python3
# -*- coding:UTF-8 -*-
# @Date    : 2020-11-18 21:56:35
# @Author  : Shenchucheng (shenchucheng@126.com)
# @Desc    :


import sys 
import logging
import json
import io 
import asyncio
import aiohttp
import aiofiles


# aiohttp.BasicAuth(user, password)
class BaseClient:
    def __init__(self, *tasks, loop=None, session=None, \
        interval=60,  headers=None):
        self.tasks = tasks
        self.loop = loop
        self.session = session 
        if not headers:
            headers = {
                'X-Requested-With': 'Pushgateway Python Client', 
                'Content-type': 'application/text'
            }
        self.headers = headers

    async def get_metrics(self, url, params=None, **kwargs):
        if not self.session:
            self.session = aiohttp.ClientSession()
        try:
            async with self.session.get(url, params=params, **kwargs) as resp:
                status, content = resp.status, await resp.read()
                return status, content
        except Exception as e:
            return -1, e

    async def post_metrics(self, url, data, auth=None, **kwargs):
        try:
            async with self.session.post(url, data=data, \
                headers=self.headers, auth=auth, **kwargs) as resp:
                status, content = resp.status, await resp.read()
                return status, content
        except Exception as e:
            return -1, e

    async def task(self, get, post, *kwargs):
        print(get)
        status, data = await self.get_metrics(**get)
        
        if status != 200:
            logging.info("Fail to get the metics agrs {}, \
                status_code: {}".format(get, status))
            data = io.BytesIO(b'prom_metrics_fail_python_client 1\n')
        print(post)
        try:
            status, ret = await self.post_metrics(**post, data=data)
        except Exception as e:
            status, ret = -1, e
        return status, ret

    def get_loop(self):
        if not self.loop:
            try:
                loop = asyncio.get_running_loop()
            except:
                loop = asyncio.get_event_loop()
            self.loop = loop
        return self.loop

    def __del__(self):
        loop = self.get_loop()
        loop.run_until_complete(self.session.close())


class StaticClient(BaseClient):
    def add_task(self, get, post):
        loop = self.get_loop()
        loop.create_task(self.run_task_forever(get, post))

    async def run_task_forever(self, get, post, interval=60):
        while 1:
            sleep = asyncio.sleep(interval)
            r =  await self.task(get, post)
            print(r)
            await sleep

        


# yaml is not necessary
class yaml:
    @staticmethod
    def load(stream, Loader=None):
        global yaml
        try:
            yaml = __import__('yaml')
        except ImportError:
            logging.exception('You have not installed yaml, '\
                'if continue, please install package "pyyaml" and try again, '\
                'and you can use json alternatively')
            sys.exit(-1)
        return yaml.load(stream, Loader=Loader)


async def load_file(filename: str, encoding=None, Loader=None, **kwargs):
    if filename.endswith('.yml') or filename.endswith('.yaml'):
        filetype = 0
    elif filename.endswith('json'):
        filetype = 1
    else:
        logging.error('Config file only support json or yaml, '\
            'please check the file {}'.format(filename) )
        sys.exit(1)
    async with aiofiles.open(filename, encoding=encoding) as f:
        content = await f.read()
        if filetype == 0:
            configs = yaml.load(content, Loader=Loader)
        else:
            configs = json.loads(content, **kwargs)
    return configs


async def load_config(filename: str, encoding=None, Loader=None, **kwargs):
    configs = await load_file(filename, encoding=None, Loader=None, **kwargs)
    session = aiohttp.ClientSession()
    loop = asyncio.get_running_loop()
    # basic configs
    check_configs_type(configs, [('global', dict), ('scrape_configs', list)])
    g_configs = configs['global']
    s_configs = configs['scrape_configs']

    # global configs 
    check_configs_type(g_configs, [('pushgateway', dict), ('external_labels', dict)])
    g_pushgateway     = g_configs['pushgateway']
    g_external_labels = g_configs['external_labels']
    g_scrape_timeout  = g_configs.get('scrape_timeout', '5s')
    g_metrics_path    = g_configs.get('g_metrics_path', '/metrics')
    g_scheme          = g_configs.get('scheme', 'http')
    g_basic_auth      = gen_basic_auth(g_configs.get('basic_auth'))
    g_scrape_interval = g_configs.get('scrape_interval', '1m')
    g_scrape_interval = max(time_convert(g_scrape_interval), 30)
    g_scrape_timeout  = time_convert(g_scrape_timeout)

    # pushgateway configs
    check_configs_type(g_pushgateway, [('target', str)])
    target       = g_pushgateway['target']
    scheme       = g_pushgateway.get('scheme', g_scheme)
    metrics_path = g_pushgateway.get('metrics_path', g_metrics_path)
    basic_auth   = g_pushgateway.get('basic_auth', g_basic_auth)
    p_timeout    = g_pushgateway.get('timeout', g_scrape_timeout)
    p_timeout    = time_convert(p_timeout)
    target.strip('/')
    if '/' in target:
        raise ValueError('Target could not contain "/", {}'.format(target))
    if not metrics_path.startswith('/'):
        metrics_path = '/' + metrics_path
    p_url = '{}://{}{}'.format(scheme, target, metrics_path)
    logging.info('Pushgateway server: {}'.format(p_url))
    p_basic_auth = gen_basic_auth(basic_auth) or g_basic_auth
    
    # scrape_configs
    for job in s_configs:
        # TODO check type
        # if not (type(job) is dict):
        #     raise TypeError()
        check_configs_type(job, [('job_name', str)])
        j_job_name        = job["job_name"]
        j_params          = job.get('params')
        j_timeout         = job.get('timeout', g_scrape_timeout)
        j_scheme          = job.get('scheme', g_scheme)
        j_static_configs  = job.get('static_configs')
        j_file_sd_configs = job.get('file_sd_configs')
        j_relabel_configs = job.get('relabel_configs')
        j_metrics_path    = job.get('metrics_path', g_metrics_path)
        j_scrape_interval = job.get('scrape_interval', g_scrape_interval)
        j_scrape_interval = time_convert(j_scrape_interval)
        j_timeout         = time_convert(j_timeout)
        j_basic_auth      = gen_basic_auth(job.get('basic_auth')) or g_basic_auth
        j_url_format      = "{}://{}{}".format(j_scheme, '{}', j_metrics_path)

        if j_static_configs:
            client = StaticClient(session=session, loop=loop)
            for static in j_static_configs:
                t_labels = g_external_labels.copy()
                _labels = static.get('labels')
                if _labels is not None:
                    t_labels.update(_labels)
                t_labels['job']              = j_job_name
                t_labels['__scheme__']       = j_scheme
                t_labels['__metrics_path__'] = j_metrics_path
                if j_params:
                    for key in j_params.keys():
                        t_labels['__param_{}'.format(key)] = j_params[key]

                for target in static['targets']:
                    __target                    = {}
                    _t_labels                   = t_labels.copy()
                    _t_labels['__address__']    = target
                    _t_labels['__param_target'] = target
                    _t_labels['instance']       = target
                    __target['labels']          = _t_labels
                    __target['timeout']         = j_timeout
                    __target['basic_auth']      = j_basic_auth
                    relabel(__target['labels'], j_relabel_configs)
                    t_url  = j_url_format.format(_t_labels['__address__'])
                    params = parse_params(_t_labels)
                    get = {
                        'url': t_url, 
                        'params': params, 
                        'auth': __target['basic_auth'],
                        'timeout': __target['timeout']
                    }
                    post = {
                        'url': '/'.join((p_url, '/'.join('/'.join(i) for i in parse_labels(_t_labels)))),
                        'auth': p_basic_auth,
                        'timeout': p_timeout
                    }
                    loop.create_task(client.run_task_forever(get, post)) 
                    

        if j_file_sd_configs:
            for file in j_file_sd_configs:
                j_refresh_interval = file.get('refresh_interval', 0)
                j_refresh_interval = time_convert(j_refresh_interval)
                t_labels = g_external_labels.copy()
                t_labels['job']              = j_job_name
                t_labels['__scheme__']       = j_scheme
                t_labels['__metrics_path__'] = j_metrics_path
                if j_params:
                    for key in j_params.keys():
                        t_labels['__param_{}'.format(key)] = j_params[key]

                for filename in file.get('files'):
                    jobs = await load_file(filename)
                    for job in jobs:
                        _t_labels = t_labels.copy()
                        _labels   = job.get('labels')
                        if _labels is not None:
                            if _labels.get('job'):
                                _labels['jobname'] = _labels.pop('job')
                            _t_labels.update(_labels)
                        for target in job.get('targets'):
                            __target = {}
                            _t_labels['__address__']    = target
                            _t_labels['__param_target'] = target
                            _t_labels['instance']       = target
                            __target['labels']          = _t_labels
                            __target['timeout']         = j_timeout
                            __target['basic_auth']      = j_basic_auth
                            relabel(__target['labels'], j_relabel_configs)
                            t_url  = j_url_format.format(_t_labels['__address__'])
                            params = parse_params(_t_labels)
                            get = {
                                'url': t_url, 
                                'params': params, 
                                'auth': __target['basic_auth'],
                                'timeout': __target['timeout']
                            }
                            post = {
                                'url': '/'.join((p_url, '/'.join('/'.join(i) for i in parse_labels(_t_labels)))),
                                'auth': p_basic_auth,
                                'timeout': p_timeout
                            }
                            loop.create_task(client.run_task_forever(get, post)) 
    return loop
            


def time_convert(times: str):
    try:
        times = float(times)
    except ValueError:
        end = times[-1]
        if end == 's':
            return time_convert(times[:-1])
        elif end == 'm':
            return time_convert(times[:-1])*60
        else:
            times = 5
    return max(5, times)
    

def relabel(labels, relabel_configs):
    if relabel_configs:
        for relabel in relabel_configs:
            target_label = relabel['target_label']
            if relabel.get('source_labels'):
                for source_label in relabel['source_labels']:
                    labels[source_label] = labels[target_label]
            elif relabel.get('replacement'):
                labels[target_label] = relabel['replacement']


def parse_params(labels: dict):
    params = {}
    for key in labels.keys():
        if key.startswith('__param_'):
            val = labels[key]
            params[key[8:]] = val 
    return params


def parse_labels(labels: dict):
    _labels = {}
    for key in labels.keys():
        if key.startswith('__'):
            continue
        _labels[key] = labels[key]
    _labels = list(_labels.items())
    _labels.sort(key=labels_sorted)
    return _labels

  
LABELS_ORDER = {
    'job': 0,
    'owner': 1,
    'instance': 3,
}

def labels_sorted(x):
    return LABELS_ORDER.get(x[0], 10)


def gen_basic_auth(basic_auth):
    if type(basic_auth) is dict:
        username = basic_auth.get('username')
        password = basic_auth.get('password')
        if username and password:
            basic_auth = aiohttp.BasicAuth(username, password)
        else:
            basic_auth = None
    else:
        basic_auth = None
    return basic_auth


def check_configs_type(configs, checks):
    # checks: [('global', dict), ('scrape_configs', list)]
    for key, _type in checks:
        try:
            val = configs[key]
            if not val:
                raise ValueError('{} is not allow'.format(val))
            if not issubclass(type(val), _type):
                raise TypeError('Type of {} must {} not {}'.format(
            key, _type, type(val)))

        except KeyError:
            logging.exception('Fail to check the configs, {} is needed'.format(key))
            sys.exit(-1)

        except (ValueError, TypeError) as e:
            logging.exception('Fail to check the configs, {}'.format(e))
            sys.exit(-1)

def main():
    client = BaseClient()
    def test():
        loop = asyncio.get_event_loop()
        tasks = [
            client.task( 
                "http://localhost:9100/metrics", 
                "http://monitor.api.test.metadl.com/metrics/job/python_test/instance/localhost:9100/status/fail"
            ),
            client.task(
                "http://localhost:9090/metrics",
                "http://monitor.api.test.metadl.com/metrics/job/python_test/instance/localhost:9090/status/ok"
            ) 
        ]
        task =  asyncio.wait(tasks, timeout=10)
        ret = loop.run_until_complete(task)
        return ret
    return test()

if __name__ == "__main__":
    main()

