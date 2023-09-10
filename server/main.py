import logging
import os
import sys

logging.basicConfig(format='[%(asctime)s]: %(message)s', datefmt='%d-%b-%y %H:%M:%S')

if __name__ == "__main__":
    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    os.chdir(dname)

    try:
        import sparkchat_api_pb2
    except ModuleNotFoundError:
        raise RuntimeError("Python protobuf code not found! Please follow the procedure to generate the python code.")
    
    import sparkchatserver
    