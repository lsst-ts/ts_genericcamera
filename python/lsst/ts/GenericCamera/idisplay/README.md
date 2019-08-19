# gencam-idisplay


Python Virtual Environment
==========================

>$ mkdir app; cd app

>$ pip3.7 install virtualenv

>$ virtualenv idisplayenv

>$ source myprojectenv/bin/activate

>$ pip install coloredlogs Flask Jinja2 watchdog uWSGI Werkzeug pywebview PyGObject pycairo

>$ pip list

List of python packages in your python virtual environment will now be:

    Package       Version
    ------------- -------
    argh          0.26.2 
    Click         7.0    
    coloredlogs   10.0   
    Flask         1.1.1  
    humanfriendly 4.18   
    itsdangerous  1.1.0  
    Jinja2        2.10.1 
    MarkupSafe    1.1.1  
    pathtools     0.1.2  
    pip           19.2.1 
    pycairo       1.18.1 
    PyGObject     3.32.2 
    pywebview     3.0.1  
    PyYAML        5.1.2  
    setuptools    41.0.1 
    uWSGI         2.0.18 
    watchdog      0.9.0  
    Werkzeug      0.15.5 
    wheel         0.33.4 

>$ git clone https://github.com/jbuffill/gencam-idisplay

>$ cd idisplay

>$ python imgdisplay.py



Linux Centos-7 Required installs
=================================

Need to verify or yum install following packages:

    centos 7 Package  
    ----------------------------------
    gobject-introspection-devel-1.56.1-1.el7.x86_64 
    cairo-devel.x86_64
    cairo-gobject.x86_64
    cairo-gobject-devel-1.15.12-3.el7.x86_64 
    pycairo.x86_64 : Python bindings for the cairo library
    gobject-introspection-devel-1.56.1-1.el7.x86_64 Mon 15 Jul 2019 12:45:11 PM MST
    gtk3
