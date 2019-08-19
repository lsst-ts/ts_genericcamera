import os, sys
import queue, threading
import coloredlogs, logging

from watchdog.events import PatternMatchingEventHandler
from watchdog.observers import Observer

log_format = '<%(levelname)s><%(levelno)s><%(filename)s:%(lineno)s><%(threadName)s><%(funcName)s()> %(message)s'
coloredlogs.DEFAULT_FIELD_STYLES={'levelname' :{'color':214,'bright':True}, 
                                  'levelno'   :{'color':214,'bright':True}, 
                                  'filename'  :{'color':'green','bright':True}, 
                                  'lineno'    :{'color':'green','bright':True}, 
                                  'threadName':{'color':'blue','bright':True},
                                  'className' :{'color':'cyan','bright':True}, 
                                  'funcName'  :{'color':'cyan','bright':True}, 
                                  'message'   :{'color':140,'bright':True}
                                 }

class DirectoryMonitor(object):
    # Class Attributes
    #--------------------
    _files_for_rendering = None
    _mqueue = queue.Queue(maxsize=10)
    _runner = None

    def __init__(self, runner=None):
        self.dirmon_log = logging.getLogger('DirMon')
        coloredlogs.install(level='SUCCESS', fmt=log_format, logger=self.dirmon_log)

        self._cn = {'className':self.__class__.__name__} # assign custom log record descriptor
        
        self._patterns = ["*.jpg"]
        # Default parameter values for PatternMatchingEventHandler
        #   self.ignore_patterns = ""
        #   self.ignore_directories = False
        #   self.case_sensitive = True
        
        self._previous_max_ts = 0
        self._previous_max_file = ''

        if runner != None:
            self._runner = runner
            self._dir_path = self._runner._path
        # if not self._mqueue:
        #     self._mqueue = queue.Queue(maxsize=10)
        
        self._observer = Observer()
        self._observer.setName('DirMonObserverThread')
        self.dirmon_log.debug(f"Observer created") # MainThread

        # handler interrupts on modified AND newly created files so don't need 'on_created'
        self._evt_handler = PatternMatchingEventHandler(patterns=self._patterns)
        self._evt_handler.on_modified = self.on_modified
        # self._evt_handler.on_created = self.on_created

    @classmethod
    def get_files(cls):
        return cls()

    def on_created(self, event):
        self.dirmon_log.debug(f"¡Created File!: {event.src_path}") # DirMonObserverThread
        self.process(event)

    def on_modified(self, event):
        self.dirmon_log.debug(f"¡Modified File!: {event.src_path}") # DirMonObserverThread
        self.process(event)

    def process(self, event=None):
        """
        event.event_type   => 'modified' | 'created' | 'moved' | 'deleted'
        event.is_directory =>True | False
        event.src_path     => path/to/observed/file
        """
        self.dirmon_log.debug(f"") # DirMonObserverThread
        
        self._files_for_rendering = self.collect_files(event)
        self.dirmon_log.debug(f'files to render:')
        self.dirmon_log.debug(f'# files to render: {self._files_for_rendering}')

        [self._mqueue.put(f) for f in self._files_for_rendering]
        self.dirmon_log.debug(f'# of items: {self._mqueue.qsize()}')
        self._runner.setFlag()

    def collect_files(self, event=None):

        if event:
            files = [f for f in [event.src_path]]
        else: # event is None when called from start_monitor
            import glob
            # pattern match on jpg files (per rules of the Unix shell)
            files = glob.glob(f"{self._dir_path}/*.jpg")
        
        tail = list()
        for f in files:
            # strip off & grab just the file name
            _, tmp_tail = os.path.split(f) # _ is just a 'don't care' for head
            tail.append(tmp_tail)
        self.dirmon_log.debug(f"splits: {tail}")

        files_dict = dict([(f, os.path.getmtime(f))
                           for f in tail
                              # files of newer ts than max
                           if (os.path.getmtime(f) > self._previous_max_ts) or 
                              # files of equal ts as max with different name
                              (os.path.getmtime(f) == self._previous_max_ts and f != self._previous_max_file)]
                         )
        self.dirmon_log.debug(f'Collected Files: {files_dict.keys()}')

        try:
            # Save the oldest ts and corresponding file
            self._previous_max_file, self._previous_max_ts = max(files_dict.items())
        except ValueError:
            self.dirmon_log.error('Collected Files not recognized as NEW or MODIFIED')

        return list(files_dict.keys())

    def start_monitor(self):
        """Starts monitoring the specified directory in a background thread."""
        self._observer.start()
        self.dirmon_log.debug(f"ObserverThread started")

        for  path in [self._dir_path]:
            if os.path.isdir(path):
                self._observer.schedule(self._evt_handler, path, recursive=True)
                self.dirmon_log.debug(f"Directory Monitor started for {path}")
                # collect initial set of existing files
                self.process()
            else:
                self.dirmon_log.debug(f"Directory: {path} is invalid!")

    def stop_monitor(self):
        """Tells watchdog to stop watching the directory."""
        self.dirmon_log.debug("Observer Stopped") # MainThread

        # Blocks thread until terminated
        self._observer.stop()
        self._observer.join()

    # Future maybe
    # -------------------------------
    # def on_moved(self, event):
    #     self.logger.debug(f"{event.src_path} moved to {event.dest_path}")
    #     pass

    # def on_deleted(self, event):
    #     self.logger.debug(f"{event.src_path} was deleted")
    #     pass

class DirMonRunner(object):
    # Class Attributes
    #--------------------
    _flag = 0

    def __init__(self, dir_path=None):
        self.runner_log = logging.getLogger('DirMonRunner')
        coloredlogs.install(level='CRITICAL', fmt=log_format, logger=self.runner_log)

        self._cn = {'className':self.__class__.__name__} # assign custom log record descriptor
        
        # Get cwd if a dir not provided
        self._path = dir_path if dir_path != None else os.getcwd()

        self._dirMonitor = DirectoryMonitor(self)
        self._dirMonitor.start_monitor()

    def setFlag(self):
        self._flag = 1
        self.runner_log.debug('Flag set')

    def run(self):
        """Initiate directory monitor"""
        self.runner_log.debug(f"Runner started") # MainThread

        try:
            while True:
                # flag 0 when waiting for new image files
                if self._flag == 1:
                    self._flag = 0
        except KeyboardInterrupt:
            self.runner_log.debug("Directory Monitoring Runner will be halted!")

        self._dirMonitor.stop_monitor()

def filemonmain():
    filemonmain_log = logging.getLogger('DirectoryMonitor')
    coloredlogs.install(level='DEBUG', fmt=log_format, logger=filemonmain_log)
    filemonmain_log.debug("filemonmain")

    # create DirectoryMonitorRunner
    runner = DirMonRunner()
    
    try:
        # start DirectoryMonitorRunner
        runner.run()
    except Exception:
        # self.logger.exception provides: (1) exception type (2) error message and (3) stacktrace
        filemonmain_log.exception("Unhandled Exception from Main!")

    sys.exit()

if __name__ == '__main__':
    filemonmain()

