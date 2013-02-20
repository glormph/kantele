import os

class Files(object):
    def __init__(self, postdata):
        self.data = postdata

    def incoming_files(self):
        filelist = self.data['pastefiles']
        if filelist == '':
            filelist = []
        else:
            filelist = [ x.strip() for x in filelist.strip().split('\n') ]
        if 'selectfiles' in self.data:
            filelist.extend(self.data.getlist('selectfiles'))
        self.filelist = [ os.path.splitext(x) for x in filelist ]
    
    def check_file_formatting(self):
        forbidden = set(['/','\\','?','.','\%','*',':','|','\"','<','>','\''])
        self.forbidden_found = []
        for fn in self.filelist:
            print fn
            if len(forbidden.intersection(fn[0]))>0:
                self.forbidden_found.append(forbidden.intersection(fn[0]))

        if self.forbidden_found:
            self.forbidden_found = \
                    set([y for x in self.forbidden_found for y in x])
            return False
        else:
            return True
