def decode(code):
    if len(code)==2:
        return tuple(code)
    return (code[0],code[1],decode(code[2]))

print(decode([1,2,[1,2,[1,2]]]))