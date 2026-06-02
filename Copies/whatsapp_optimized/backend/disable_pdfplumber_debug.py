"""
Monkey-patch pdfplumber to disable debug output before it's imported.
This runs BEFORE pdfplumber loads.
"""
import sys
import io

# Create a null writer that discards all output
class NullWriter(io.StringIO):
    def write(self, s):
        return len(s)  # Pretend we wrote it
    def flush(self):
        pass

# Monkey-patch the pdfminer modules before they're imported
import logging
for name in ['pdfminer', 'pdfminer.pdfpage', 'pdfminer.converter',
             'pdfminer.pdfinterp', 'pdfminer.psparser', 'pdfminer.pdfdocument']:
    log = logging.getLogger(name)
    log.setLevel(logging.CRITICAL)
    for handler in log.handlers[:]:
        log.removeHandler(handler)
    log.addHandler(logging.NullHandler())
    log.propagate = False
