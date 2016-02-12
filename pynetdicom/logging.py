
from io import BytesIO

def wrap_list(lst, prefix='  ', items_per_line=16, max_size=None):
    lines = []
    if isinstance(lst, BytesIO):
        lst = lst.getvalue()
    
    cutoff_output = False
    byte_count = 0
    for i in range(0, len(lst), items_per_line):
        chunk = lst[i:i + items_per_line]
        byte_count += len(chunk)
        
        if max_size is not None:
            if byte_count <= max_size:
                line = prefix + '  '.join(format(x, '02x') for x in chunk)
                lines.append(line)
            else:
                cutoff_output = True
                break
        else:
            line = prefix + '  '.join(format(x, '02x') for x in chunk)
            lines.append(line)
    
    if cutoff_output:
        lines.insert(0, prefix + 'Only dumping %s bytes.' %max_size)
    
    return lines
