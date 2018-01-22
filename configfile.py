#! /usr/bin/python

# Uses json to save a dictionary of optionally encrypted configuration
# information in the user's home directory.

# When creating the configuration a password must be supplied if you want the 
# configuration to be encypted. If no password is supplied, the config file will 
# be created unencypted.
# If the file is encypted, then initialization will result in an exception
# if no password is supplied when opening.
# No effort is made to obscure secret data within memory. Due to Python's immutable
# string types this would likely require calls to an external C module.

# The file is encrypted with AES and uses a password based key derivation function
# (PBJDF2) to generate the encryption key.

# 2012-10-09 Paul T Sparks

import errno
import os
import os.path
import json
import sys

from pbkdf2 import PBKDF2
from Crypto.Cipher import AES

BLOCK_SIZE = 16  # 128 bit blocks
IV_SIZE = 16 # 128-bits to initialise
KEY_SIZE = 32 # 256-bit key
SALT_SIZE = 8 # 64-bits of salt

# TODO write to file as updates made.
# TODO Document usage for passing secure values (e.g. wipe after storage)

# Get full filepath from filename passed in.
# TODO allow full path for filename
def _getPath(filename):
    homeDir= os.path.expanduser('~')
    return homeDir + os.sep + filename

def exists(filename):
    """Returns true if configration file exists."""
    return os.path.exists(_getPath(filename))

class ConfigFile():
    """
    """
    # Try to open the config file. If the file
    def __init__(self, filename, password=None, defaults=None):
        self.properties = {}
        self.password = password
        if defaults: self.properties = defaults
        self.configFilename = _getPath(filename)
            
        try:
            configFile = open(self.configFilename, 'rb')
            contents = configFile.read()
            configFile.close()
        except IOError as e:
            if errno.ENOENT != e.errno:
                raise IOError("Error opening configuration file %s:%s" % 
                               (self.configFilename,sys.exc_info()) )
            dirpath = os.path.dirname(self.configFilename)
            if not os.path.exists(dirpath):
                os.makedirs(dirpath, 0o700)
            self._save()
            os.chmod(self.configFilename, 0o600)
            return
        except:
            raise RuntimeError("Unexpected error opening configuration file %s:%s" % 
                               (self.configFilename,sys.exc_info()) )

        if contents[0] == '{' and contents[-1] == '}': # not encrypted
            self.properties= json.loads(contents)
            return;

        if len(contents) < (SALT_SIZE + IV_SIZE):
            raise IOError("File corrupted %s" % self.configFilename)
        if not password:
            raise ValueError('Password required for encrypted file')
        contents = self.decrypt(contents, password)
        if contents[0] == '{' and contents[-1] == '}': # decryption success
            self.properties= json.loads(contents)
            return;
        raise ValueError('Wrong password')



    def _save(self):
        if self.password:
            data = self.encrypt(json.dumps(self.properties), self.password)
        else:
            data = json.dumps(self.properties)
        with open(self.configFilename, 'w') as f:
            f.write(data)
    
    def get(self):
        """ Return configuration as a dictionary """
        return self.properties

    def __getitem__(self, key):
        return self.properties[key]

    def __len__(self):
        return len(self.properties)

    def __setitem__(self, key, val):
        self.properties[key]= val
        self._save()

    def __repr__(self):
        return str(self.properties)

    def has_key(self, key):
        return self.properties.has_key(key)


    def encrypt(self, plaintext, passphrase):
        ''' Pad plaintext with spaces, then encrypt it with a new, randomly initialised cipher. 
        Will not preserve trailing whitespace in plaintext!'''
        initVector = os.urandom(IV_SIZE)
        salt = os.urandom(SALT_SIZE)
        key = PBKDF2(passphrase, salt).read(KEY_SIZE)
        cipher = AES.new(key, AES.MODE_CBC, initVector)
        return salt + initVector + cipher.encrypt(plaintext + ' '*(BLOCK_SIZE - (len(plaintext) % BLOCK_SIZE)))

    def decrypt(self, ciphertext, passphrase):
        ''' Reconstruct the cipher object and decrypt. Will not preserve trailing 
        whitespace in the retrieved value!'''
        salt = ciphertext[:SALT_SIZE]
        initVector = ciphertext[SALT_SIZE:SALT_SIZE + IV_SIZE]
        ciphertext = ciphertext[SALT_SIZE + IV_SIZE:]
        key = PBKDF2(passphrase, salt).read(KEY_SIZE)
        cipher = AES.new(key, AES.MODE_CBC, initVector)
        return cipher.decrypt(ciphertext).rstrip(' ')


if __name__ == "__main__":
    config = configfile('configfile.conf', defaults={'test1':'val1', 'test2':'val2'})
    print config.get()
    config.save()
    
