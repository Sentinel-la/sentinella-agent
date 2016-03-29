import logging
import os
import re
import time

logging.basicConfig(level=logging.DEBUG)

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger(__name__)

def get_openstack_events(agent):

    class TailFile(FileSystemEventHandler):

        def __init__(self, agent):
            super(TailFile, self).__init__()
            self.agent = agent
            self.config = agent.config['openstack_logs']
            self.filenames = list(set([agent._config['openstack_services'][service]['log'].strip() for service in agent._config['openstack_services'] if agent._config['openstack_services'][service] is not False and agent._config['openstack_services'][service] != '']))
            self.regex = self.config['parser']['regex']
            self.allowed_events = ['CRITICAL', 'WARNING', 'ERROR']
            self.hostname = os.uname()[1].split('.')[0]
            self.log_services = {}
            [self.log_services.update({agent._config['openstack_services'][service]['log']: service}) for service in agent._config['openstack_services'] if agent._config['openstack_services'][service] is not False and agent._config['openstack_services'][service] != '']
            self.f = {}
            self.filenames_ln = []
            self.file_data = {}
            for filename in self.filenames:
                logger.info(filename)
                is_file = os.path.isfile(filename)
                is_link = os.path.islink(filename)
                if is_file or is_link:
                    logger.debug(filename)
                    self.f[filename] = open(filename, 'r')
                    self.f[filename].seek(0, 2)
                else:
                    logger.info('get_openstack_events: couldn\'t read file "%s" , are the filename/permissions correct?', filename)
                if is_link:
                    symlink = os.readlink(filename)
                    self.filenames_ln.append(symlink)
                    self.file_data[symlink] = filename

        def reopen(self, filename):
            self.f[filename].close()
            self.f[filename] = open(filename, 'r')

        def on_created(self, event):
            if event.src_path in self.filenames:
                logger.debug('file recreated, reopen')
                self.reopen(event.src_path)

        def on_modified(self, event):
            if event.src_path in self.filenames or event.src_path in self.filenames_ln:
                identifier = event.src_path
                if event.src_path not in self.f.keys():
                    identifier = self.file_data[event.src_path]
                service_name = self.log_services[identifier]
                while True:
                    line = self.f[identifier].readline()

                    if not line:
                        break
                    try:
                        log_line = re.match(self.regex, line)
                        
                        if log_line:
                            log_line = log_line.groupdict()
                            if log_line['level'] in self.allowed_events:
                                log_line['server_name'] = self.hostname
                                log_line['service_name'] = service_name
                                logger.debug(log_line)
                                self.agent.push_log(log_line)
                    except Exception, e:
                        logger.exception('cannot parse log line : ' + line)

    agent.run_event.wait()


    config = agent.config['openstack_logs']

    filenames = list(set([agent._config['openstack_services'][service]['log'] for service in agent._config['openstack_services'] if agent._config['openstack_services'][service] is not False and agent._config['openstack_services'][service] != '']))
    directories = list(set([os.path.dirname(filename) for filename in filenames]))

    observer = {}
    event_handler = {}

    for directory in directories:
        if os.path.isdir(directory):
            event_handler[directory] = TailFile(agent)
            observer[directory] = Observer()
            observer[directory].schedule(event_handler[directory], directory, recursive=False)
            try:
                observer[directory].start()
            except Exception, e:
                logger.info(e)
        else:
            logger.info('get_openstack_events: couldn\'t read directory '+directory+' , are the directory name/permissions correct?')

    while agent.run_event.is_set():
        time.sleep(1)

    for directory in observer.keys():
        observer[directory].stop()
        observer[directory].join()

    logger.info('get_openstack_events terminated')