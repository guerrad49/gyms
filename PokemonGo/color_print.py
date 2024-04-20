# TODO: not sure if this should be a class anymore

class ColorPrint:
    '''A class for simplifying the inclusion of color to print()'''
    
    OKCYAN    = '\033[96m'
    WARNING   = '\033[93m'
    OKGREEN   = '\033[92m'
    FAIL      = '\033[91m'
    BOLD      = '\033[1m'
    ENDC      = '\033[0m'

    def __init__(self, msg):
        self.msg = msg

    def proc(self):
        print('{}{}{}'.format(self.OKCYAN, self.msg, self.ENDC))

    def ok(self):
        print('{}{}{}'.format(self.OKGREEN, self.msg, self.ENDC))

    def warning(self):
        print('{}{}{}'.format(self.WARNING, self.msg, self.ENDC))

    def fail(self):
        print('{}{}{}{}'.format(self.FAIL, self.BOLD, self.msg, self.ENDC))