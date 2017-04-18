import numpy
import shuffle
import cPickle as pkl
import gzip


def fopen(filename, mode='r'):
    if filename.endswith('.gz'):
        return gzip.open(filename, mode)
    return open(filename, mode)


class TreeTextIterator:
    """Simple Bitext iterator."""
    def __init__(self, source, target,
                 source_dict, target_dict, sourcetree,
                 batch_size=128,
                 maxlen=100,
                 n_words_source=-1,
                 n_words_target=-1,
                 shuffle_each_epoch=False):
        if shuffle_each_epoch:
            shuffle.main([source, target, sourcetree])
            self.source = fopen(source+'.shuf', 'r')
            self.target = fopen(target+'.shuf', 'r')
            self.source_tree = fopen(sourcetree+'.shuf', 'r')
        else:
            self.source = fopen(source, 'r')
            self.target = fopen(target, 'r')
            self.source_tree = fopen(sourcetree, 'r')
        with open(source_dict, 'rb') as f:
            self.source_dict = pkl.load(f)
        with open(target_dict, 'rb') as f:
            self.target_dict = pkl.load(f)

        self.shuffle = shuffle_each_epoch

        self.batch_size = batch_size
        self.maxlen = maxlen

        self.n_words_source = n_words_source
        self.n_words_target = n_words_target

        self.source_buffer = []
        self.source_tree_buffer = []
        self.target_buffer = []
        self.k = batch_size * 20

        self.end_of_data = False

    def __iter__(self):
        return self

    def reset(self):
        if self.shuffle:
            shuffle.main([self.source.name.replace('.shuf', ''), self.target.name.replace('.shuf', ''), self.source_tree.name.replace('.shuf', '')])
            self.source = fopen(self.source.name, 'r')
            self.target = fopen(self.target.name, 'r')
            self.source_tree = fopen(self.source_tree.name, 'r')
        else:
            self.source.seek(0)
            self.target.seek(0)
            self.source_tree.seek(0)

    def next(self):
        if self.end_of_data:
            self.end_of_data = False
            self.reset()
            raise StopIteration

        source = []
        source_tree = []
        target = []

        # fill buffer, if it's empty
        assert len(self.source_buffer) == len(self.target_buffer), 'Buffer size mismatch!'

        if len(self.source_buffer) == 0:
            for k_ in xrange(self.k):         # batch_size * 20 buffer
                ss = self.source.readline()
                ss_tree = self.source_tree.readline()
                if ss == "":
                    break
                tt = self.target.readline()
                if tt == "":
                    break

                self.source_buffer.append(ss.strip().split())    # split by space
                self.source_tree_buffer.append(ss_tree.strip().split())
                self.target_buffer.append(tt.strip().split())

            # sort by target buffer
            tlen = numpy.array([len(t) for t in self.target_buffer])
            tidx = tlen.argsort()     # e.g. array([1,3,2,8,4]) => array([0, 2, 1, 4, 3])

            _sbuf = [self.source_buffer[i] for i in tidx]
            _s_treebuf = [self.source_tree_buffer[i] for i in tidx]
            _tbuf = [self.target_buffer[i] for i in tidx]

            self.source_buffer = _sbuf
            self.source_tree_buffer = _s_treebuf
            self.target_buffer = _tbuf

        if len(self.source_buffer) == 0 or len(self.target_buffer) == 0:
            self.end_of_data = False
            self.reset()
            raise StopIteration

        try:

            # actual work here
            while True:

                # read from source file and map to word index  worddict['eos'] = 0 worddict['UNK'] = 1
                try:
                    ss = self.source_buffer.pop()
                    ss_tree = self.source_tree_buffer.pop()
                except IndexError:
                    break
                ss = [self.source_dict[w] if w in self.source_dict else 1
                      for w in ss]
                if self.n_words_source > 0:
                    ss = [w if w < self.n_words_source else 1 for w in ss]

                # read from target file and map to word index
                tt = self.target_buffer.pop()
                tt = [self.target_dict[w] if w in self.target_dict else 1
                      for w in tt]
                if self.n_words_target > 0:
                    tt = [w if w < self.n_words_target else 1 for w in tt]

                if len(ss) > self.maxlen and len(tt) > self.maxlen:
                    continue

                source.append(ss)
                source_tree.append(ss_tree)
                target.append(tt)

                if len(source) >= self.batch_size or \
                        len(target) >= self.batch_size:
                    break
        except IOError:
            self.end_of_data = True

        if len(source) <= 0 or len(target) <= 0:
            self.end_of_data = False
            self.reset()
            raise StopIteration

        return source, target, source_tree
