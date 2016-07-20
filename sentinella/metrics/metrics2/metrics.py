import os
import platform
import trollius as asyncio
from trollius import From
import psutil
import logging
from cpuinfo import cpuinfo
from novaclient import client
import subprocess

logger = logging.getLogger(__name__)

frequency = 60
hostname = os.uname()[1].split('.')[0]

@asyncio.coroutine
def get_server_usage_stats(agent):
    yield From(agent.run_event.wait())
    config = agent.config['metrics']
    logger.info('starting "get_server_usage" task for "%s"', hostname)
    
    prev_stats = psutil.disk_io_counters(perdisk=True)
    prev_io_counters = psutil.net_io_counters(pernic=True)
    
    disk_partitions = psutil.disk_partitions()
    partition_mountpoint = dict()
    partitions = set()

    included_partitions = [part.device for part in disk_partitions]

    for dp in disk_partitions:
        if included_partitions and dp.device not in included_partitions:
            continue
        partitions.add(dp.device)
        partition_mountpoint[dp.device] = dp.mountpoint
    while agent.run_event.is_set():
        yield From(asyncio.sleep(frequency))
        try:
            cpu_percent = psutil.cpu_percent(interval=None)
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            loadavg = os.getloadavg()
            
            data = {'server_name': hostname, 'measurements': [], 'stats':{'platform': {}, 'hardware': {}, 'openstack': {}}}

            #data['measurements'].append({'name': 'cpu.total', 'value': psutil.cpu_count()})
            data['measurements'].append({'name': 'cpu.percent', 'value': cpu_percent})

            #data['measurements'].append({'name': 'memory.total', 'value': memory.total})
            data['measurements'].append({'name': 'memory.available', 'value': memory.available})
            data['measurements'].append({'name': 'memory.percent', 'value': memory.percent})
            data['measurements'].append({'name': 'memory.used', 'value': memory.used})
            data['measurements'].append({'name': 'memory.free', 'value': memory.free})
            
            #data['measurements'].append({'name': 'swap.total', 'value': swap.total})
            data['measurements'].append({'name': 'swap.used', 'value': swap.used})
            data['measurements'].append({'name': 'swap.free', 'value': swap.free})
            data['measurements'].append({'name': 'swap.percent', 'value': swap.percent})
            
            data['measurements'].append({'name': 'loadavg.1', 'value': loadavg[0]})
            data['measurements'].append({'name': 'loadavg.5', 'value': loadavg[1]})
            data['measurements'].append({'name': 'loadavg.15', 'value': loadavg[2]})
            
            curr_stats = psutil.disk_io_counters(perdisk=True)
            include_disks = None
            
                
            include_disks = [part.device for part in disk_partitions]

            for disk in curr_stats:
                if include_disks and disk not in include_disks:
                    continue

                curr = curr_stats[disk]
                prev = prev_stats[disk]
                
                data['measurements'].append({'name': 'disk_io.read_count', 'tags': {'disk': disk}, 'value': curr.read_count - prev.read_count})
                data['measurements'].append({'name': 'disk_io.write_count', 'tags': {'disk': disk}, 'value': curr.write_count - prev.write_count})
                data['measurements'].append({'name': 'disk_io.read_bytes', 'tags': {'disk': disk}, 'value': curr.read_bytes - prev.read_bytes})
                data['measurements'].append({'name': 'disk_io.write_bytes', 'tags': {'disk': disk}, 'value': curr.write_bytes - prev.write_bytes})
                data['measurements'].append({'name': 'disk_io.read_time', 'tags': {'disk': disk}, 'value': curr.read_time - prev.read_time})
                data['measurements'].append({'name': 'disk_io.write_time', 'tags': {'disk': disk}, 'value': curr.write_time - prev.write_time})

            prev_stats = curr_stats
            
            for partition in partitions:
                disk_data = psutil.disk_usage(partition_mountpoint[partition])
                data['measurements'].append({'name': 'partition_usage.total', 'tags': {'partition': partition}, 'value': disk_data.total})
                data['measurements'].append({'name': 'partition_usage.used', 'tags': {'partition': partition}, 'value': disk_data.used})
                data['measurements'].append({'name': 'partition_usage.free', 'tags': {'partition': partition}, 'value': disk_data.free})
                data['measurements'].append({'name': 'partition_usage.percent', 'tags': {'partition': partition}, 'value': disk_data.percent})
                
            curr_io_counters = psutil.net_io_counters(pernic=True)

            for interface in curr_io_counters:
                try:
		    curr = curr_io_counters[interface]
                except:
                    curr = 0

                try:
                    prev = prev_io_counters[interface]
                except:
                    prev = 0

                data['measurements'].append({'name': 'net_io.bytes_sent', 'tags': {'interface': interface}, 'value': curr.bytes_sent - prev.bytes_sent})
                data['measurements'].append({'name': 'net_io.bytes_recv', 'tags': {'interface': interface}, 'value': curr.bytes_recv - prev.bytes_recv})
                data['measurements'].append({'name': 'net_io.packets_sent', 'tags': {'interface': interface}, 'value': curr.packets_sent - prev.packets_sent})
                data['measurements'].append({'name': 'net_io.packets_recv', 'tags': {'interface': interface}, 'value': curr.packets_recv - prev.packets_recv})
                data['measurements'].append({'name': 'net_io.errin', 'tags': {'interface': interface}, 'value': curr.errin - prev.errin})
                data['measurements'].append({'name': 'net_io.errout', 'tags': {'interface': interface}, 'value': curr.errout - prev.errout})
                data['measurements'].append({'name': 'net_io.dropin', 'tags': {'interface': interface}, 'value': curr.dropin - prev.dropin})
                data['measurements'].append({'name': 'net_io.dropout', 'tags': {'interface': interface}, 'value': curr.dropout - prev.dropout})

            server_stats = platform.dist()
        
            data['stats']['platform']['dist'] = platform.dist()[0] + ' ' + platform.dist()[1] + ' ' + platform.dist()[2]
            data['stats']['platform']['kernel'] = platform.uname()[2]
            data['stats']['platform']['architecture'] = platform.architecture()[0]
            
            cpu_hw = cpuinfo.get_cpu_info()
            
            data['stats']['platform']['processor'] = {}
            data['stats']['platform']['processor']['qty'] = psutil.cpu_count()
            data['stats']['platform']['processor']['brand'] = cpuinfo.get_cpu_info()['brand']
            data['stats']['platform']['processor']['count'] = cpuinfo.get_cpu_info()['count']
            data['stats']['platform']['processor']['flags'] = cpuinfo.get_cpu_info()['flags']
            
            data['stats']['platform']['memory'] = {}
            data['stats']['platform']['memory']['total'] = memory.total
            
            data['stats']['platform']['swap'] = {}
            data['stats']['platform']['swap']['total'] = swap.total

            p = subprocess.Popen(["nova-manage", "version"], stdout=subprocess.PIPE)
            version = p.communicate()[0]

            if version:
                data['stats']['openstack']['version'] = version.strip()

            # OpenStack processes
            processes = agent.processes
            processes_to_check = processes
            for p in psutil.process_iter():
                try:                        
                    try:
                        process_name = p.name()
                    except:
                        process_name = p.name
                    if process_name in processes_to_check:
                        if p.is_running():
                            is_running = 1
                        else:
                            is_running = 0
                        
                        data['measurements'].append({'name': 'openstack.processes.'+process_name+'.'+'cpu_percent', 'value': p.cpu_percent()})
                        data['measurements'].append({'name': 'openstack.processes.'+process_name+'.'+'memory_percent', 'value': p.memory_percent()})
                        data['measurements'].append({'name': 'openstack.processes.'+process_name+'.'+'num_threads', 'value': p.num_threads()})
                        data['measurements'].append({'name': 'openstack.processes.'+process_name+'.'+'is_running', 'value': is_running})
                        #data['measurements'].append({'name': 'openstack.processes.'+process_name+'.'+'create_time', 'value': create_time})
                        
                        if p.is_running() and p.status != psutil.STATUS_ZOMBIE:
                            process_status = 1
                        else:
                            process_status = 0
                            
                        data['measurements'].append({'name': 'openstack.processes.'+process_name+'.'+'up', 'tags': {'status': p.status()} ,'value': process_status})
                    
                        processes_to_check.remove(process_name)
                except psutil.Error:
                    pass
                
            for process in processes_to_check:
                data['measurements'].append({'name': 'openstack.processes.'+process+'.'+'up', 'tags': {'status': 'down'}, 'value': 0})

            # OpenStack Nova API
            if agent._config['openstack_credentials']['user'] and agent._config['openstack_credentials']['password'] and agent._config['openstack_credentials']['project'] and agent._config['openstack_credentials']['auth_url']:
                nova = client.Client(agent.nova_api_version, agent._config['openstack_credentials']['user'], agent._config['openstack_credentials']['password'], agent._config['openstack_credentials']['project'], agent._config['openstack_credentials']['auth_url'])

                if nova:
                    #nova services
                    services = nova.services.list()

                    for service in services:
                        status = 1 if service.state == 'up' else 0
                        data['measurements'].append({'name': 'openstack.nova-api.services.'+service.binary+'.'+'status', 'value': status})

                    #availability zones
                    avalability_zones = nova.availability_zones.list(True)
                    for availability_zone in avalability_zones:
                        status = 1 if availability_zone.zoneState['available'] is True else 0
                        data['measurements'].append({'name': 'openstack.nova-api.avalability_zones.status', 'tags': {'availability_zone': availability_zone.zoneName}, 'value': status})
                    
                    #hypervisor stats
                    hypervisor_keys = {'count', 'current_workload', 'disk_available_least', 'free_disk_gb', 'free_ram_mb', 'local_gb', 'local_gb_used', 'memory_mb', 'memory_mb_used', 'running_vms', 'vcpus', 'vcpus_used'}
                    stats = nova.hypervisor_stats.statistics()

                    for key_name in hypervisor_keys:
                        if hasattr(stats, key_name):
                            data['measurements'].append({'name': 'openstack.nova-api.hypervisor_total.'+key_name, 'value': getattr(stats, key_name)})

                    if hasattr(stats, 'vcpus') and hasattr(stats, 'vcpus_used'):
                        data['measurements'].append({'name': 'openstack.nova-api.hypervisor_total.vcpus_percent', 'value': round(100 * float(stats.vcpus_used)/float(stats.vcpus), 2)})

                    if hasattr(stats, 'local_gb') and hasattr(stats, 'local_gb_used'):
                        data['measurements'].append({'name': 'openstack.nova-api.hypervisor_total.local_gb_percent', 'value': round(100 * float(stats.local_gb_used)/float(stats.local_gb), 2)})

                    if hasattr(stats, 'memory_mb') and hasattr(stats, 'memory_mb_used'):
                        data['measurements'].append({'name': 'openstack.nova-api.hypervisor_total.memory_mb_percent', 'value': round(100 * float(stats.memory_mb_used)/float(stats.memory_mb), 2)})

                    #server stats
                    servers = nova.servers.list()
                    for server in servers:
                        value = agent.openstack_status[server.status]
                        if not value:
                            value = -1
                        data['measurements'].append({'name': 'openstack.nova-api.servers', 'tags': {'name': server.name, 'id': server.id, 'tenant_id': server.tenant_id, 'status': server.status}, 'value': value})

                    #hypervisor specific stats
                    hypervisor_keys = {'current_workload', 'disk_available_least', 'free_disk_gb', 'free_ram_mb', 'local_gb', 'local_gb_used', 'memory_mb', 'memory_mb_used', 'running_vms', 'vcpus', 'vcpus_used'}
                    hypervisors = nova.hypervisors.list()
                    for hypervisor in hypervisors:
                        if hypervisor.status == 'enabled':
                            for key_name in hypervisor_keys:
                                if hasattr(hypervisor, key_name):
                                    data['measurements'].append({'name': 'openstack.nova-api.hypervisors.'+availability_zone.zoneName, 'tags': {'hypervisor': hypervisor.hypervisor_hostname, 'name': key_name}, 'value': getattr(stats, key_name)})

            logger.debug('{}: server_usage={}%'.format(hostname, data))
            yield From(agent.async_push(data))
            prev_io_counters = curr_io_counters
        except:
            logger.exception('cannot get the server usage')
    logger.info('get_server_usage terminated')
