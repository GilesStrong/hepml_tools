from __future__ import division

import numpy as np
import types
import pandas

'''
Todo:
- Ammend HEP yielder to work with categorical features
- Include getFeature in FoldYielder
- Tidy code and move to PEP 8
- Add docstrings and stuff
- Add method to FoldYielder to import other data into correct format, e.g. csv
- Generalise get_fold_df
'''

class FoldYielder():
    def __init__(self, datafile=None, n_cats=0):
        self.n_cats = n_cats
        self.augmented = False
        self.aug_mult = 0
        self.train_time_aug = False
        self.test_time_aug = False
        if not isinstance(datafile, type(None)):
            self.add_source(datafile, self.n_cats)

    def add_source(self, datafile, n_cats=0):
        self.source = datafile
        self.n_folds = len(self.source)
        self.n_cats = n_cats

    def get_fold(self, index, datafile=None):
        if isinstance(datafile, type(None)):
            datafile = self.source

        index = str(index)
        weights = None
        if 'fold_' + index + '/weights' in datafile:
            weights = np.array(datafile['fold_' + index + '/weights'])
        if 'fold_' + index + '/targets' in datafile:
            targets = np.array(datafile['fold_' + index + '/targets'])
        
        if self.n_cats:
            inputs = []
            all_inputs = np.array(datafile['fold_' + index + '/inputs'])
            for i in range(self.n_cats):
                inputs.append(all_inputs[:,i])
            inputs.append(all_inputs[:,i+1:])
            
        else:
            inputs = np.array(datafile['fold_' + index + '/inputs'])
            
        return {'inputs':inputs,
                'targets':targets,
                'weights':weights}

    def get_fold_df(self, index, datafile=None, preds=None, weightName='weights'):
        if isinstance(datafile, type(None)):
            datafile = self.source

        index = str(index)
        data = pandas.DataFrame()
        if 'fold_' + index + '/' + weightName in datafile:
            data['gen_weight'] = np.array(datafile['fold_' + index + '/' + weightName])
        if 'fold_' + index + '/targets' in datafile:
            data['gen_target'] = np.array(datafile['fold_' + index + '/targets'])
        if not isinstance(preds, type(None)):
            data['pred_class'] = preds
        return data

class HEPAugFold(FoldYielder):
    def __init__(self, header, datafile=None, input_pipe=None,
                 rotate=True, reflect=True, rot_mult=4,
                 train_time_aug=True, test_time_aug=True):
        self.header = header
        self.rotate_aug = rotate
        self.reflect_aug = reflect
        self.augmented = True
        self.rot_mult = rot_mult
        
        if self.rotate_aug and not self.reflect_aug:
            self.aug_mult = self.rot_mult
            
        elif not self.rotate_aug and self.reflect_aug:
            self.reflect_axes = ['_px', '_py', '_pz']
            self.aug_mult = 8
            
        elif not self.rotate_aug and not self.reflect_aug:
            self.augmented = False
            train_time_aug = False
            test_time_aug = False
            self.aug_mult = 0
            print ('No augmentation specified!')
            input_pipe = None
            self.get_test_fold = self.get_fold
            
        else: #reflect and rotate
            self.reflect_axes = ['_px', '_pz']
            self.aug_mult = self.rot_mult*4
            
        self.train_time_aug = train_time_aug
        self.test_time_aug = test_time_aug
        self.input_pipe = input_pipe
        
        if not isinstance(datafile, type(None)):
            self.add_source(datafile)
    
    def rotate(self, in_data, vectors):
        for vector in vectors:
            in_data.loc[:, vector + '_pxtmp'] = in_data.loc[:, vector + '_px']*np.cos(in_data.loc[:, 'aug_angle'])-in_data.loc[:, vector + '_py']*np.sin(in_data.loc[:, 'aug_angle'])
            in_data.loc[:, vector + '_py'] = in_data.loc[:, vector + '_py']*np.cos(in_data.loc[:, 'aug_angle'])+in_data.loc[:, vector + '_px']*np.sin(in_data.loc[:, 'aug_angle'])
            in_data.loc[:, vector + '_px'] = in_data.loc[:, vector + '_pxtmp']
    
    def reflect(self, in_data, vectors):
        for vector in vectors:
            for coord in self.reflect_axes:
                try:
                    cut = (in_data['aug' + coord] == 1)
                    in_data.loc[cut, vector + coord] = -in_data.loc[cut, vector + coord]
                except KeyError:
                    pass
            
    def get_fold(self, index, datafile=None):
        if isinstance(datafile, type(None)):
            datafile = self.source
            
        index = str(index)
        weights = None
        targets = None
        if 'fold_' + index + '/weights' in datafile:
            weights = np.array(datafile['fold_' + index + '/weights'])
        if 'fold_' + index + '/targets' in datafile:
            targets = np.array(datafile['fold_' + index + '/targets'])
            
        if not self.augmented:
            return {'inputs':np.array(datafile['fold_' + index + '/inputs']),
                    'targets':targets,
                    'weights':weights}

        if isinstance(self.input_pipe, type(None)):
            inputs = pandas.DataFrame(np.array(datafile['fold_' + index + '/inputs']), columns=self.header)
        else:
            inputs = pandas.DataFrame(self.input_pipe.inverse_transform(np.array(datafile['fold_' + index + '/inputs'])), columns=self.header)            
        
        vectors = [x[:-3] for x in inputs.columns if '_px' in x]
        if self.rotate_aug:
            inputs['aug_angle'] = 2*np.pi*np.random.random(size=len(inputs))
            self.rotate(inputs, vectors)
            
        if self.reflect_aug:
            for coord in self.reflect_axes:
                inputs['aug' + coord] = np.random.randint(0, 2, size=len(inputs))
            self.reflect(inputs, vectors)
            
        if isinstance(self.input_pipe, type(None)):
            inputs = inputs[self.header].values
        else:
            inputs = self.input_pipe.transform(inputs[self.header].values)
        
        return {'inputs':inputs,
                'targets':targets,
                'weights':weights}
    
    def get_test_fold(self, index, augIndex, datafile=None):
        if augIndex >= self.aug_mult:
            print ("Invalid augmentation index passed", augIndex)
            return -1
        
        if isinstance(datafile, type(None)):
            datafile = self.source
            
        index = str(index)
        weights = None
        targets = None
        if 'fold_' + index + '/weights' in datafile:
            weights = np.array(datafile['fold_' + index + '/weights'])
        if 'fold_' + index + '/targets' in datafile:
            targets = np.array(datafile['fold_' + index + '/targets'])
            
        if isinstance(self.input_pipe, type(None)):
            inputs = pandas.DataFrame(np.array(datafile['fold_' + index + '/inputs']), columns=self.header)
        else:
            inputs = pandas.DataFrame(self.input_pipe.inverse_transform(np.array(datafile['fold_' + index + '/inputs'])), columns=self.header)            
            
        if self.reflect_aug and self.rotate_aug:
            rotIndex = augIndex%self.rot_mult
            ref_index = '{0:02b}'.format(int(augIndex/4))
            vectors = [x[:-3] for x in inputs.columns if '_px' in x]
            inputs['aug_angle'] = np.linspace(0, 2*np.pi, (self.rot_mult)+1)[rotIndex]
            for i, coord in enumerate(self.reflect_axes):
                inputs['aug' + coord] = int(ref_index[i])
            self.rotate(inputs, vectors)
            self.reflect(inputs, vectors)
            
        elif self.reflect_aug:
            ref_index = '{0:03b}'.format(int(augIndex))
            vectors = [x[:-3] for x in inputs.columns if '_px' in x]
            for i, coord in enumerate(self.reflect_axes):
                inputs['aug' + coord] = int(ref_index[i])
            self.reflect(inputs, vectors)
            
        else:
            vectors = [x[:-3] for x in inputs.columns if '_px' in x]
            inputs['aug_angle'] = np.linspace(0, 2*np.pi, (self.rot_mult)+1)[augIndex]
            self.rotate(inputs, vectors)
            
        if isinstance(self.input_pipe, type(None)):
            inputs = inputs[self.header].values
        else:
            inputs = self.input_pipe.transform(inputs[self.header].values)

        return {'inputs':inputs,
                'targets':targets,
                'weights':weights}
