import asyncio
import psutil
import logging


logger = logging.getLogger(__name__)


@asyncio.coroutine
def get_cpu_usage(agent):
    yield from agent.run_event.wait()
    config = agent.config['linux']
    logger.info('starting "get_cpu_usage" task for "%s"', config['hostname'])
    db_config = config['database']
    yield from agent.async_create_database(**db_config)

    while agent.run_event.is_set():
        yield from asyncio.sleep(config['cpu_usage_frequency'])
        try:
            cpu_percent = psutil.cpu_percent(interval=None)
            points = [{
                'measurement': 'cpu_usage',
                'tags': {
                    'host': config['hostname'],
                },
                'fields': {
                    'value': cpu_percent
                }
            }]
            logger.debug('{}: cpu_usage={}%'.format(
                         config['hostname'],
                         cpu_percent))
            yield from agent.async_push(points, db_config['name'])
        except:
            logger.exception('cannot get the cpu usage')
    logger.info('get_cpu_usage terminated')


@asyncio.coroutine
def get_memory_usage(agent):
    yield from agent.run_event.wait()
    config = agent.config['linux']
    logger.info('starting "get_memory_usage" task for "%s"',
                config['hostname'])
    db_config = config['database']
    yield from agent.async_create_database(**db_config)

    while agent.run_event.is_set():
        yield from asyncio.sleep(config['memory_usage_frequency'])
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()

            points = [{
                'measurement': 'memory_usage',
                'tags': {
                    'host': config['hostname'],
                },
                'fields': {
                    'v_available': memory.available,
                    'v_percent': memory.percent,
                    'v_used': memory.used,
                    'v_free': memory.free,
                    's_used': swap.used,
                    's_free': swap.free,
                    's_percent': swap.percent
                }
            }]
            logger.debug('{}: memory_usage: memory={}%, swap={}%'.format(
                         config['hostname'],
                         memory.percent,
                         swap.percent))
            yield from agent.async_push(points, db_config['name'])
        except:
            logger.exception('cannot get the memory usage')
    logger.info('get_memory_usage terminated')


@asyncio.coroutine
def get_disks_io_stats(agent):
    yield from agent.run_event.wait()
    config = agent.config['linux']
    db_config = config['database']

    logger.info('starting "get_disks_io_stats" task for "%s"',
                config['hostname'])

    yield from agent.async_create_database(**db_config)

    prev_stats = psutil.disk_io_counters(perdisk=True)

    while agent.run_event.is_set():
        yield from asyncio.sleep(config['disks_io_stats_frequency'])
        try:
            curr_stats = psutil.disk_io_counters(perdisk=True)
            include_disks = None
            if 'include_disks' in config:
                include_disks = config['include_disks']
            points = []
            for disk in curr_stats:
                if include_disks and disk not in include_disks:
                    continue
                curr = curr_stats[disk]
                prev = prev_stats[disk]
                points.append({
                    'measurement': 'disk_io_stats',
                    'tags': {
                        'host': config['hostname'],
                        'disk': disk
                    },
                    'fields': {
                        'read_count': curr.read_count - prev.read_count,
                        'write_count': curr.write_count - prev.write_count,
                        'read_bytes': curr.read_bytes - prev.read_bytes,
                        'write_bytes': curr.write_bytes - prev.write_bytes,
                        'read_time': curr.read_time - prev.read_time,
                        'write_time': curr.write_time - prev.write_time,
                    }
                })
            yield from agent.async_push(points, db_config['name'])
            prev_stats = curr_stats
        except:
            logger.exception('cannot get the disk io stats')
    logger.info('get_disks_io_stats terminated')


@asyncio.coroutine
def get_disks_usage(agent):
    yield from agent.run_event.wait()
    config = agent.config['linux']
    db_config = config['database']
    logger.info('starting "get_disks_usage" task for "%s"',
                config['hostname'])

    yield from agent.async_create_database(**db_config)

    disk_partitions = psutil.disk_partitions()
    partition_mountpoint = dict()
    partitions = set()
    included_partitions = None
    if 'include_partitions' in config:
        included_partitions = set(config['include_partitions'])

    for dp in disk_partitions:
        if included_partitions and dp.device not in included_partitions:
            continue
        partitions.add(dp.device)
        partition_mountpoint[dp.device] = dp.mountpoint

    while agent.run_event.is_set():
        yield from asyncio.sleep(config['disks_usage_frequency'])
        try:
            points = []
            for partition in partitions:
                data = psutil.disk_usage(partition_mountpoint[partition])
                points.append({
                    'measurement': 'disks_usage',
                    'tags': {
                        'host': config['hostname'],
                        'partition': partition
                    },
                    'fields': {
                        'total': data.total,
                        'used': data.used,
                        'free': data.free,
                        'percent': data.percent
                    }
                })
            yield from agent.async_push(points, db_config['name'])
        except:
            logger.exception('cannot get the disk usage')
    logger.info('get_disks_usage terminated')


@asyncio.coroutine
def get_network_usage(agent):
    yield from agent.run_event.wait()
    config = agent.config['linux']
    db_config = config['database']
    logger.info('starting "get_disks_usage" task for "%s"',
                config['hostname'])

    yield from agent.async_create_database(**db_config)

    prev_io_counters = psutil.net_io_counters(pernic=True)

    while agent.run_event.is_set():
        yield from asyncio.sleep(config['network_usage_frequency'])
        try:
            curr_io_counters = psutil.net_io_counters(pernic=True)
            points = []

            for interface in curr_io_counters:
                curr = curr_io_counters[interface]
                prev = prev_io_counters[interface]
                data = {
                    'measurement': 'net_io_stats',
                    'tags': {
                        'host': config['hostname'],
                        'interface': interface
                    },
                    'fields': {
                        'bytes_sent': curr.bytes_sent - prev.bytes_sent,
                        'bytes_recv': curr.bytes_recv - prev.bytes_recv,
                        'packets_sent': curr.packets_sent - prev.packets_sent,
                        'packets_recv': curr.packets_recv - prev.packets_recv,
                        'errin': curr.errin - prev.errin,
                        'errout': curr.errout - prev.errout,
                        'dropin': curr.dropin - prev.dropin,
                        'dropout': curr.dropout - prev.dropout
                    }
                }
                points.append(data)

            yield from agent.async_push(points, db_config['name'])
            prev_io_counters = curr_io_counters
        except:
            logger.exception('cannot get the bet io stats')
    logger.info('get_net_io_stats terminated')
