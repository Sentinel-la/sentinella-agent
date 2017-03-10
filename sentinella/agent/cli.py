#!/usr/bin/env python
from importlib import import_module
import json
import sys
import os
import pip
import urllib2
from shutil import copyfile
import zipfile

try:
    from urllib.request import urlopen
except ImportError:
    from urllib import urlopen

import click

AGENT_VERSION = '0.5.4'

PY34_PLUS = sys.version_info[0] == 3 and sys.version_info[1] >= 4
PY27 = sys.version_info[0] == 2 and sys.version_info[1] == 7

LOG_FORMAT_EX = '%(asctime)s %(levelname)s [%(name)s %(filename)s:'\
    '%(funcName)s:%(lineno)d] %(message)s'
LOG_FORMAT_NO = '%(asctime)s %(levelname)s %(message)s'
LOG_FILENAME = '/var/log/sentinella/sentinella.log'

INDEX_FILE_URL = 'https://raw.githubusercontent.com/Sentinel-la/'\
    'sentinella-agent/master/meta/plugin_index.json'

API_SENTINELLA = "https://api.sentinel.la"

def get_index():
    data = urlopen(INDEX_FILE_URL).read()
    if PY34_PLUS:
        data = data.decode()

    index = {k: v for (k, v) in json.loads(data).items()
             if PY34_PLUS and v['py3'] or PY27 and v['py2']}
    return index


@click.group()
@click.version_option(version=AGENT_VERSION)
@click.option('--config',
              '-c',
              type=click.Path(exists=False,
                              file_okay=True,
                              dir_okay=False,
                              writable=False,
                              resolve_path=True),
              default='/etc/sentinella/sentinella.conf',
              help='specify a different config file',
              metavar='<config_file>')
@click.option('--pidfile',
              '-p',
              type=click.Path(exists=False,
                              file_okay=True,
                              dir_okay=False,
                              writable=False,
                              resolve_path=True),
              default='/var/run/sentinella/sentinella.pid',
              help='specify a different pidfile file',
              metavar='<pidfile_file>')
def cli(config, pidfile):
    """sentinella: send OpenStack logs and metrics to Sentinel.la"""
    pass


@cli.command()
@click.pass_context
def init(ctx):
    """initialize the sentinella agent configuration"""
    config_file = ctx.parent.params['config']
    
    mon_list = [{'nova': [{'nova-api': {'process': 'nova-api', 'log': '/var/log/nova/nova-api.log'}},
                          {'nova-scheduler': {'process': 'nova-scheduler', 'log': '/var/log/nova/nova-scheduler.log'}},
                          {'nova-compute': {'process': 'nova-compute', 'log': '/var/log/nova/nova-compute.log'}},
                          {'nova-cert': {'process': 'nova-cert', 'log': '/var/log/nova/nova-cert.log'}},
                          {'nova-conductor': {'process': 'nova-conductor', 'log': '/var/log/nova/nova-conductor.log'}},
                          {'nova-novncproxy': {'process': 'nova-novncproxy', 'log': '/var/log/nova/nova-novncproxy.log'}}
                        ]},
                {'neutron': [{'neutron-server': {'process': 'neutron-server', 'log': '/var/log/neutron/server.log'}},
                             {'neutron-dhcp-agent': {'process': 'neutron-dhcp-agent', 'log': '/var/log/neutron/dhcp-agent.log'}},
                             {'neutron-openvswitch-agent': {'process': 'neutron-openvswitch-agent', 'log': '/var/log/neutron/openvswitch-agent.log'}},
                             {'neutron-l3-agent': {'process': 'neutron-l3-agent', 'log': '/var/log/neutron/l3-agent.log'}},
                             {'neutron-metadata-agent': {'process': 'neutron-metadata-agent', 'log': '/var/log/neutron/metadata-agent.log'}}
                        ]}
                ]
    
    responses = {'api_url': API_SENTINELLA,
                 'log_format': '',
                 'log_file': '/var/log/sentinella/sentinella.log',
                 'log_level': 'INFO',
                 'plugins_conf_dir': '/etc/sentinella/conf.d',
                 'openstack_services': {}, 'openstack_credentials': {},
                 'plugins': {'sentinella.metrics': ['get_server_usage_stats'],
                             'sentinella.openstack_logs': ['get_openstack_events']}}

    click.echo(click.style('\nSentinel.la agent configuration\n',
                           fg='blue', bold=True, underline=True))
    
    configure = click.prompt('\nDo you want to configure the parameters now?', default='yes', type=bool)
    if not configure:
        click.echo(click.style('You can configure sentinella later by running:\nsentinella init\n', fg='magenta'))
        sys.exit()
    
    responses['account_key'] = click.prompt('Enter your Account Key', default='', confirmation_prompt=True)
    
    if not responses['account_key']:
        click.echo(click.style('\nConfiguration aborted, Account Key missing\n', fg='red'))
        click.echo(click.style('You can configure sentinella later by running:\nsentinella init\n', fg='magenta'))
        sys.exit()
    
    proxy = click.prompt('\nIf the server has no direct Internet connection you can configure a HTTPS proxy.\nDo you want to configure it now?', default='no', type=bool)

    if proxy is True:
        responses['proxy'] = {}
        responses['proxy']['host'] = click.prompt('Enter your proxy host (ip or hostname)', show_default=False, default='')
        responses['proxy']['port'] = click.prompt('Enter your proxy port', show_default=False, default='')
        
        proxy_use_password = click.prompt('\nDo you want to configure proxy auth (user and password)?', default='no', type=bool)
        
        if proxy_use_password is True:
            responses['proxy']['user'] = click.prompt('Enter your proxy auth user', show_default=False, default='')
            responses['proxy']['password'] = click.prompt('Enter your proxy auth password', hide_input=True, confirmation_prompt=True, default='')
    
    click.echo(click.style('\nOpenStack configuration\n',
                           fg='magenta', underline=True))
    
    responses['openstack_credentials']['user'] = click.prompt('Enter OpenStack user', default='admin')
    
    if not responses['openstack_credentials']['user']:
        click.echo(click.style('\nConfiguration aborted, OpenStack user missing\n', fg='red'))
        click.echo(click.style('You can configure sentinella later by running:\nsentinella init\n', fg='magenta'))
        sys.exit()
        
    responses['openstack_credentials']['password'] = click.prompt('Enter OpenStack password', hide_input=True, confirmation_prompt=True, default='')

    if not responses['openstack_credentials']['password']:
        click.echo(click.style('\nConfiguration aborted, OpenStack password missing\n', fg='red'))
        click.echo(click.style('You can configure sentinella later by running:\nsentinella init\n', fg='magenta'))
        sys.exit()
        
    responses['openstack_credentials']['project'] = click.prompt('Enter OpenStack project', default='admin')
    
    if not responses['openstack_credentials']['project']:
        click.echo(click.style('\nConfiguration aborted, OpenStack project missing\n', fg='red'))
        click.echo(click.style('You can configure sentinella later by running:\nsentinella init\n', fg='magenta'))
        sys.exit()
        
    responses['openstack_credentials']['auth_url'] = click.prompt('Enter OpenStack auth url [http://<keystone_endpoint_ip>:35357/v2.0]', show_default=False, default='')
    
    if not responses['openstack_credentials']['auth_url']:
        click.echo(click.style('\nConfiguration aborted, OpenStack auth url missing\n', fg='red'))
        click.echo(click.style('You can configure sentinella later by running:\nsentinella init\n', fg='magenta'))
        sys.exit()

    for item in mon_list:
        component = item.keys()
        for service_items in item.values():
            for service_item in service_items:
                service = service_item.keys()[0]
                values = service_item.values()[0]

                responses['openstack_services'][service] = click.prompt('\nMonitor ' + service + '?', default='yes', type=bool)
                
                if responses['openstack_services'][service]:
                    responses['openstack_services'][service] = {}
                    responses['openstack_services'][service]['process'] = click.prompt('Name of the ' + values['process'] + ' process', default=values['process'], type=str)
                    responses['openstack_services'][service]['log'] = click.prompt(service + ' log file', default=values['log'])

    with open(config_file, 'w') as f:
        json.dump(responses, f, indent=4)

    click.echo(click.style('\nconfiguration file generated successfully\n', fg='green'))


@cli.command()
@click.pass_context
@click.option('--compact', default=False, is_flag=True)
def list(ctx, compact):
    """list available sentinella plugins"""
    index = get_index()

    top = '+{:<20}+{:<5}+{:<60}+{:<35}+-+'.format('-' * 20,
                                                  '-' * 5,
                                                  '-' * 60,
                                                  '-' * 35)
    header = '|{:<20}|{:<5}|{:<60}|{:<35}|F|'.format('name',
                                                     'ver.',
                                                     'description',
                                                     'author')
    line = '|{:<20}|{:<5}|{:<60}|{:<35}|{}|'

    if not compact:
        print(top)
        print(header)
        print(top)

    for name, meta in index.items():
        if not compact:
            print(line.format(name, meta['version'], meta['description'],
                              meta['author'], '*' if meta['featured'] else ''))
        else:
            print(name)
    if not compact:
        print(top)


@cli.command()
@click.pass_context
@click.argument('plugin', nargs=1, required=True)
@click.argument('version', nargs=1, required=True)
def install(ctx, plugin, version):

    plugin_directory = os.path.realpath(__file__)
    plugin_directory = plugin_directory[:-12]
    
    """
     1.- Dowload plugin
    """

    # URL to download plugin.
    source_plugin = "http://sf-c01.sentinel.la:5580/plugins/download/"

    # Name plugin wiht version
    name_plugin = plugin

    # Extension file
    extension = "zip"

    file_plugin = name_plugin + "-" + version + "." + extension
    url = source_plugin + file_plugin
    file_name = url.split('/')[-1]
    u = None
    try: 
        u = urllib2.urlopen(url)
    except urllib2.HTTPError, e:
        print "Repository :" + source_plugin + file_plugin +" Not found."
    except urllib2.URLError, e:
        print 'URLError = ' + str(e.reason)
    except httplib.HTTPException, e:
        print 'HTTPException'
    
    if u:
        f = open(file_name, 'wb')
        meta = u.info()
        file_size = int(meta.getheaders("Content-Length")[0])
        print "Downloading: %s Bytes: %s" % (file_name, file_size)

        file_size_dl = 0
        block_sz = 8192
        while True:
            buffer = u.read(block_sz)
            if not buffer:
                break

            file_size_dl += len(buffer)
            f.write(buffer)
            percent = (file_size_dl, file_size_dl * 100. / file_size)
            status = r"%10d  [%3.2f%%]" % percent
            status = status + chr(8)*(len(status)+1)
            print status,

        f.close()

        """
         2.- Copy file to Sentinella
        """
        copyfile("{0}".format(file_plugin), plugin_directory+file_plugin)

        """
         3.- Remove file to this directory
        """
        os.remove(file_plugin)

        """
         4.- Unzip plugin in Sentinella
        """
        zip_ref = zipfile.ZipFile( plugin_directory + file_plugin, 'r')
        zip_ref.extractall(plugin_directory)
        zip_ref.close()
        os.remove(plugin_directory+file_plugin)

        """
         5.- Copy .conf file plugin to /etc/sentinella/conf.d/
        """
        file_conf = "{0}.conf".format(name_plugin)
        origin = plugin_directory + name_plugin + '/conf/' + file_conf
        dest = "/etc/sentinella/conf.d/{}".format(file_conf)
        copyfile(origin, dest)
        
        print "Plugin " + name_plugin + " ready install into "  + plugin_directory

@cli.command()
@click.pass_context
@click.argument('plugin', nargs=1, required=True)
def upgrade(ctx, plugin):
    """upgrade sentinella plugin"""
    index = get_index()
    if plugin not in index:
        click.echo(click.style(
                   'plugin {} not found!'.format(plugin), fg='red'))
        return
    pip_args = ['install']
    meta = index[plugin]
    if 'pip_cmd' in meta:
        plugin = meta['pip_cmd']
    else:
        plugin = '{}=={}'.format(plugin, meta['version'])
    pip_args = ['install', '-U']
    pip_args.append(plugin)
    pip.main(pip_args)


@cli.command()
@click.pass_context
@click.argument('plugin', nargs=1, required=True)
def reinstall(ctx, plugin):
    """reinstall sentinella plugin"""
    index = get_index()
    if plugin not in index:
        click.echo(click.style(
                   'plugin {} not found!'.format(plugin), fg='red'))
        return
    pip_args = ['install']
    meta = index[plugin]
    if 'pip_cmd' in meta:
        plugin = meta['pip_cmd']
    else:
        plugin = '{}=={}'.format(plugin, meta['version'])
    pip_args = ['install', '--force-reinstall', '-U']
    pip_args.append(plugin)
    pip.main(pip_args)


@cli.command()
@click.pass_context
def show(ctx):
    """show the list of enabled plugins"""
    try:
        config_file = ctx.parent.params['config']
        with open(config_file, 'r') as f:
            config = json.load(f)
    except Exception, e:
        click.echo('Invalid config: check permissions and/or if the config contains valid JSON')
        return

    if 'plugins' not in config:
        click.echo('no enabled plugins')
        return

    for key, value in config['plugins'].items():
        click.echo('module: {0} - functions: {1}'.format(
                   key, ', '.join(value)))


@cli.command()
@click.pass_context
def clear(ctx):
    """remove all plugins from configuration"""
    try:
        config_file = ctx.parent.params['config']
        with open(config_file, 'r') as f:
            config = json.load(f)
    except Exception, e:
        click.echo('Invalid config: check permissions and/or if the config contains valid JSON')
        return

    if 'plugins' in config:
        del config['plugins']
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2, sort_keys=True)

    click.echo('All plugins removed')


def validate_plugins(ctx, param, value):
    result = {}
    for v in value:
        if '=' not in v:
            raise click.BadParameter('plugin %s in not valid' % v)
        module, functions = v.replace(' ', '').split('=')
        result[module] = functions.split(',')
    return result


@cli.command(short_help='enable one or more plugins')
@click.pass_context
@click.argument('plugins', nargs=-1, required=True,
                callback=validate_plugins)
def enable(ctx, plugins):
    """Enable one or more plugins

PLUGINS are expressed in the form:

    module1.submodule1=function1,function2,... module2=function3,...

Example:

    sentinella enable sentinella.metrics=get_server_usage

Enable the function get_server_usage of the
'sentinella.metrics' plugin.
    """
    try:
        config_file = ctx.parent.params['config']
        with open(config_file, 'r') as f:
            config = json.load(f)
    except Exception, e:
        click.echo('Invalid config: check permissions and/or if the config contains valid JSON')
        return
    if 'plugins' not in config:
        config['plugins'] = {}

    for module, functions in plugins.items():
        try:
            m = import_module(module)
        except:
            click.echo('module %s does not exists' % module)
            continue
        if module not in config['plugins']:
            config['plugins'][module] = []
        for f in functions:
            if not hasattr(m, f):
                click.echo('module %s does not contains %s' % (module, f))
                continue
            if f not in config['plugins'][module]:
                config['plugins'][module].append(f)

        if len(config['plugins'][module]) == 0:
            del config['plugins'][module]

    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2, sort_keys=True)


@cli.command(short_help='disable one or more plugins')
@click.pass_context
@click.argument('plugins', nargs=-1, required=True, callback=validate_plugins)
def disable(ctx, plugins):
    """Disable one or more plugins

PLUGINS are expressed in the form:

    module1.submodule1=function1,function2,... module2=function3,...

Example:

    sentinella disable sentinella.metrics=get_server_usage

Disable the function get_server_usage of the
'sentinella.metrics' plugin
    """
    try:
        config_file = ctx.parent.params['config']
        with open(config_file, 'r') as f:
            config = json.load(f)
    except Exception, e:
        click.echo('Invalid config: check permissions and/or if the config contains valid JSON')
        return
    if 'plugins' not in config:
        return

    for module, functions in plugins.items():
        if module not in config['plugins']:
            continue
        for f in functions:
            if f in config['plugins'][module]:
                config['plugins'][module].remove(f)
        if len(config['plugins'][module]) == 0:
            del config['plugins'][module]

    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2, sort_keys=True)


@cli.command()
@click.pass_context
def run(ctx):
    """run the agent"""
    pid_file = ctx.parent.params['pidfile']
    with open(pid_file, 'w') as f:
        f.write(str(os.getpid()))
    config_file = ctx.parent.params['config']
    from sentinella.agent import Tourbillon
    ag = Tourbillon(config_file)
    ag.run()


def main():
    cli(prog_name='sentinella', standalone_mode=False)

if __name__ == '__main__':
    if __package__ is None:
        path = os.path.dirname(os.path.dirname(os.path.dirname(
                               os.path.abspath(__file__))))

        sys.path.append(path)
    main()
