import os, sys, gc, time
import queue, threading
import coloredlogs, logging

from flask import Flask, render_template, send_from_directory, make_response, redirect, url_for
import webview
import filemon.directorymonitor as mon

# Disable werkzeug HTTP request logs(e.g. 127.0.0.1 - - [02/Aug/2019 11:14:34] "GET / HTTP/1.1" 200 -)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

log_format = '<%(levelname)s><%(filename)s:%(lineno)s><%(threadName)s><%(funcName)s()> %(message)s'
coloredlogs.DEFAULT_FIELD_STYLES={'levelname' :{'color':214,'bright':True}, 
                                  'filename'  :{'color':'green','bright':True}, 
                                  'lineno'    :{'color':'green','bright':True}, 
                                  'threadName':{'color':'blue','bright':True},
                                  'className' :{'color':'cyan','bright':True}, 
                                  'funcName'  :{'color':'cyan','bright':True}, 
                                  'message'   :{'color':140,'bright':True}
                                 }
imgdisplay_log = logging.getLogger('ImgDisplay')
coloredlogs.install(level='SUCCESS', fmt=log_format, logger=imgdisplay_log)

tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)

cnt = 0
dm = None
window = None

@app.route('/')
@app.route('/<height>')
def hello(height=432):
    gc.collect()

    global cnt
    global dm

    imgdisplay_log.debug('Hello')

    if not cnt:
        dm = mon.DirectoryMonitor.get_files()
        imgdisplay_log.debug(f'cnt:qsize: {dm._mqueue.qsize()}')
        cnt+=1

    while True:
        try:
            image = dm._mqueue.get()
            imgdisplay_log.debug(f'image: {image}')
        except queue.Empty:
            pass
        else:
            if image is None:
                break
            else:
                imgdisplay_log.debug(f'else:qsize: {dm._mqueue.qsize()}')
                imgdisplay_log.debug(f'else:image: {image}')
                imgdisplay_log.debug('render')
                return render_template('img.html', image=image, maxheight=height)

@app.route('/image/<path:imgname>')
def random_image(imgname):
    return send_from_directory(os.getcwd(), imgname, as_attachment=True)

@app.route('/close/')
def close():
    """
    Adds a rudimentary "close window" function to the UI.
    """
    response = make_response('Closing window...')
    window.destroy()
    return response

def start_server(**args):
    imgdisplay_log.debug('Start_Server')
    app.run(host=args['host'], port=args['port'])

def imgdisplay_main():
    imgdisplay_log.debug('Imgdisplay')

    fm = threading.Thread(name='filemon', target=mon.filemonmain, daemon=True)
    fm.start()
    
    kwargs = {'host': 'localhost', 'port': 5432, 'width':768 , 'height': 432}
    t = threading.Thread(name='start_server', target=start_server, daemon=True, kwargs=kwargs)
    t.start()

    global window
    window = webview.create_window("Live Image View",
                                   "http://127.0.0.1:{port}".format(port=kwargs['port']),
                                   height=kwargs['height'],
                                   width=kwargs['width'],
                                   fullscreen=False,
                                   confirm_close=True
                                  )

    try:
        imgdisplay_log.debug('WebviewStart')
        webview.start()
    except Exception:
        # logging.exception provides: (1) exception type (2) error message and (3) stacktrace
        imgdisplay_log.exception("Unhandled Exception from Main!")
    except KeyboardInterrupt:
        imgdisplay_log.error("Live View & File Monitoring will be halted!")

    sys.exit()

if __name__ == '__main__':
    imgdisplay_main()
