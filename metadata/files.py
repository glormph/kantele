import os
import consts


class Files(object):
    def get_uploaded_files(self):
        try:
            filelist = os.listdir(consts.UPLOAD_DIR)
        except OSError:
            filelist = []
        return sorted(filelist)

    def load_files(self, files):
        self.pastefiles = []
        self.selectfiles = []
        if 'files' in files:
            self.allfiles = files['files']
        else:
            self.allfiles = []
        uploaded = self.get_uploaded_files()
        for fn in self.allfiles:
            fullfn = fn + self.allfiles[fn]['extension']
            if fullfn in uploaded:
                self.selectfiles.append(fullfn)
            else:
                self.pastefiles.append(fullfn)

    def post_files(self, postdata):
        filelist = postdata['pastefiles']
        if filelist == '':
            filelist = []
        else:
            filelist = [x.strip() for x in filelist.strip().split('\n')]
        if 'selectfiles' in postdata:
            filelist.extend(postdata.getlist('selectfiles'))
        self.filelist = [os.path.splitext(x) for x in filelist]

    def check_file_formatting(self):
        forbidden = set(['/', '\\', '?', '.', ',', '\%', '*', ':', '|', '\"',
                         '<', '>', '\''])
        self.forbidden_found = []
        for fn in self.filelist:
            if len(forbidden.intersection(fn[0])) > 0:
                self.forbidden_found.append(forbidden.intersection(fn[0]))

        if self.forbidden_found:
            self.forbidden_found = set([y for x in self.forbidden_found
                                        for y in x])
            return False
        else:
            return True
