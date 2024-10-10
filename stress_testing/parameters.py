import json
import random
import re
import sys

import rstr

from .functions import json_to_tuple


###############################################################################
#  PARAMETERS
###############################################################################
#
# Classes to inject dynamic values for stressing requests.
#
#  Paramaters that can be updated on multiple levels when iterating:
#   - Each request
#   - Each batch
#   - Each reference
#
# Example:
#
# parameters = Parameters({
#     "id": SequenceRequest(0),
#     "vid": Sequence(0),
#     "group": SequenceBatch(0)
# })
#

def format_parameters(parameters, string, update=True):
    re_sub = re.compile(r'<<(\w+)>>')
    def update_str(parameters, key):
        p = parameters[key]
        if update:
            if isinstance(p, Parameter):
                p.update_str()
        return str(p)
    return re_sub.sub(lambda m: update_str(parameters, m.group(1)), string)


class Parameter:
    def __init__(self, keep_state=False):
        self.keep_state = keep_state
        self.current = '<no value>'

    #def __deepcopy__(self, memo):
    #    new = self.__class__(self.keep_state)
    #    new.current = self.current
    #    return new

    # Save the current state.
    def getstate(self):
        raise NotImplementedError

    # Restore to a stored state.
    def setstate(self, state):
        raise NotImplementedError

    # Implemented by LookupValue
    # TODO: Usage unknown
    def get(self, parameters, key):
        raise NotImplementedError
    
    # Set/update from e.g. benchmarking-nso cli.
    def set(self, *args):
        raise NotImplementedError

    # Update when a new value is requested
    # and return the new value.
    def update_str(self):
        pass

    # Update the value after each request.
    def update_request(self):
        pass

    # Update after a batch of requests.
    def update_batch(self):
        pass

    # Restore to initial state.
    def reset(self):
        pass

    # Return the current value.
    def current(self):
        return None
    
    # Return the calculated value.
    # Implemented by Calc
    # TODO: Should this be merged with update_str?
    def val(self, parameters):
        raise NotImplementedError()
    
    # Return current value as a string.
    def __str__(self):
        return str(self.current)

    # Return the representative value of the parameter. 
    def __repr__(self):
        return 'Parameter{}'


class Sequence(Parameter):
    def __init__(self, n, wrap=None, keep_state=False):
        super().__init__(keep_state)
        self.n = n
        self.wrap = wrap

    def __repr__(self):
        return f'{self.__class__.__name__}(start={self.n}, wrap={self.wrap}, current={self.current})'

    def __deepcopy__(self, memo):
        return self.__class__(self.n)

    def getstate(self):
        return self.n

    def setstate(self, state):
        self.n = state

    def set(self, n):
        if isinstance(n, str):
            n = int(n)
        self.n = n

    def update_str(self):
        if self.current == '<no value>':
            self.current = self.n
        else:
            self.current += 1
            if self.wrap is not None:
                self.current = self.current % self.wrap

    def reset(self):
        self.n = 0


class SequenceRequest(Sequence):
    def __init__(self, n, wrap=None, keep_state=False):
        super().__init__(n, wrap, keep_state)

    def update_str(self):
        pass

    def update_request(self):
        super().update_str()


class SequenceBatch(Sequence):
    def __init__(self, n, keep_state=False):
        super().__init__(n, keep_state)

    def update_str(self):
        pass

    def update_batch(self):
        if self.current == '<no value>':
            self.current = self.n
        else:
            self.current += 1
            if self.wrap is not None:
                self.current = self.current % self.wrap


class SequenceRequestRandomized(SequenceRequest):
    def __init__(self, length, wrap=None, seed=None, keep_state=False):
        super().__init__(0, wrap, keep_state)
        self.length = length
        self.seed = seed
        self.rnd = random.Random(seed)
        # TODO: Maybe it is better to do this in update otherwise it will be
        # done in the runner but not used.
        self.sequence = list(range(self.length))
        self.rnd.shuffle(self.sequence)
        self.n = 0

    def __repr__(self):
        return f'SequenceRequestRandomized(seed={self.seed} length={self.length}, values left={len(self.sequence)} current={self.current})'

    def __deepcopy__(self, memo):
        return self.__class__(self.length, self.wrap, self.seed)
    
    def getstate(self):
        raise RuntimeWarning('Implementation must be update to support updating scheme')
        return (self.n, self.sequence)

    def setstate(self, state):
        # NOTE: This will restore the sequence as a tuple and will be immutable.
        # NOTE: The random generator state is not restored.
        self.n, self.sequence = state
        raise RuntimeWarning('Implementation must be update to support updating scheme')
    
    def update_request(self):
        try:
            self.current = self.sequence[self.n]
        except IndexError:
            self.current = f'<no more values>{self.n}'
        self.n += 1
        if self.wrap is not None:
            self.n = self.n % self.wrap
        


class RandomParameter(Parameter):
    def __init__(self, seed=None, keep_state=False):
        super().__init__(keep_state)
        self.seed = seed
        self.rnd = random.Random(seed)

    def getstate(self):
        return self.rnd.getstate()

    def setstate(self, state):
        self.rnd.setstate(state)


class RandomValue(RandomParameter):
    # Wrapping only works when a seed is provided
    def __init__(self, lower, upper, wrap=None, seed=None, keep_state=False):
        super().__init__(seed, keep_state)
        self.lower = lower
        self.upper = upper
        self.wrap = wrap
        self.n = 0

    def __repr__(self):
        return f'RandomValue({self.lower}..{self.upper}, n={self.n}, {self.current})'

    def __deepcopy__(self, memo):
        return self.__class__(self.lower, self.upper, self.seed)
    
    def update_str(self):
        self.n += 1
        if self.wrap is not None and self.n > self.wrap:
            self.__init__(self.lower, self.upper, self.wrap, self.seed)
        self.current = self.rnd.randint(self.lower, self.upper)



class RandomValueRequest(RandomValue):
    def __init__(self, lower, upper, wrap=None, seed=None, keep_state=False):
        super().__init__(lower, upper, wrap, seed, keep_state)

    def __repr__(self):
        return f'RandomValueRequest({self.lower}..{self.upper}, n={self.n}, {self.current})'

    def update_str(self):
        pass

    def update_request(self):
        super().update_str()
    

class RandomString(RandomParameter):
    def __init__(self, length, wrap=None, seed=None, keep_state=False):
        super().__init__(seed, keep_state)
        self.length = length
        self.rstr = rstr.Rstr(self.rnd)
        self.value = self.rstr.letters(self.length)
        self.wrap = wrap
        self.n = 0

    def __repr__(self):
        return f'{self.__class__}(seed={self.seed}, length={self.length}), current={self.current}'

    def __deepcopy__(self, memo):
        return self.__class__(self.length, self.seed)

    def getstate(self):
        return (super().getstate(), self.value)

    def setstate(self, state):
        state, self.value = state
        super().setstate(state)

    def set(self, n):
        # NOTE: This is a hack to allow changing the length of the string,
        #       but it breaks the pseudo random sequence.
        if isinstance(n, str):
            n = int(n)
        self.length = n

    def update_str(self):
        self.n += 1
        if self.wrap is not None and self.n > self.wrap:
            self.__init__(self.length, self.wrap, self.seed)
        self.current = self.rstr.letters(self.length)


class RandomStringRequest(RandomString):
    def __init__(self, length, seed=None, keep_state=False):
        super().__init__(length, seed, keep_state)

    def update_str(self):
        pass

    def update_request(self):
        super().update_str()


class LookupValue(Parameter):
    def __init__(self, values, format, attr):
        super().__init__()
        self.values = values
        self.format = format
        self.attr = attr

    def __repr__(self):
        return f'LookupValue(key={self.key})'

    def __deepcopy__(self):
        return self.__class__(self.values, self.format)
    
    def __str__(self):
        raise NotImplementedError("LoopupValue should not be converted to string")
        
    def get(self, parameters, key):
        try:
            name = format_parameters(parameters, self.format)
            inst = self.values[name]
            return inst[self.attr]
        except Exception as e:
            print(f'ERROR: {e}')
            print(f'ERROR: {self.format}')
            return "ERROR"



class Calc(Parameter):
    def __init__(self, key, wrap, mul, add):
        super().__init__()
        self.key = key
        self.wrap = wrap
        self.mul = mul
        self.add = add

    def __repr__(self):
        return f'Calc(key={self.key}, mul{self.mul}, add={self.add}, current={self.current})' 
    
    def update_str(self, parameters):
        i = parameters[self.key].n
        self.current = i//self.wrap*self.mul+self.add
    
    
"""
class Parameters is a dict of values and Parameter objects.
Makes it possible provide parameters in the form of <<x>> in
resource and data strings.
"""


class Parameters(dict):
    def set(self, d):
        for k, v in d.items():
            if k in self:
                ov = self[k]
                if isinstance(ov, Parameter):
                    ov.set(v)
                elif ov is int:
                    self[k] = int(v)
                elif ov is float:
                    self[k] = float(v)
                else:
                    self[k] = v

    def __missing__(self, key):
        return "<<" + key + ">>"

    def update_request(self):
        for v in self.values():
            if isinstance(v, Parameter):
                v.update_request()

    def update_batch(self):
        for v in self.values():
            if isinstance(v, Parameter):
                v.update_batch()

    def update_cmdline(self, cmd_p):
        if cmd_p is None:
            return
        if isinstance(cmd_p, str):
            k, v = cmd_p.split('=')
            self.update({k: v})
        elif isinstance(cmd_p, list):
            for p in cmd_p:
                k, v = p.split('=')
                self.update({k: v})
        else:
            raise TypeError(f'Invalid type: {type(cmd_p)}')

    def reset(self):
        for v in self.values():
            if isinstance(v, Parameter):
                v.reset()

    def save_state(self):
        for k,v in self.items():
            if isinstance(v, Parameter) and v.keep_state:
                with open(f'{k}.state', 'w') as f:
                    f.write(json.dumps(v.getstate()))

    def load_state(self):
        n = 0
        s = 0
        for k,v in self.items():
            if isinstance(v, Parameter) and v.keep_state:
                n += 1
                try:
                    with open(f'{k}.state', 'r') as f:
                        v.setstate(json_to_tuple(f.read()))
                        s += 1
                except FileNotFoundError:
                    pass
        if s and n != s:
            print(f'ERROR: Inconsistent states. Loaded {s} of {n} states. Remove state files to start fresh.')
            sys.exit(1)
