import re
from .mgf import MGFParser

class MGFParserPLGS(MGFParser):
    scan_regexp = re.compile('LEPeakID:(\d+):', re.IGNORECASE)