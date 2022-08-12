

import re

text_to_search = '''
abcdefghijklmnopqurtuvwxyz
ABCDEFGHIJKLMNOPQRSTUVWXYZ
1234567890
Ha HaHa
MetaCharacters (Need to be escaped):
. ^ $ * + ? { } [ ] \ | ( )
coreyms.com
321-555-4321
123.555.1234
123*555*1234
800-555-1234
900-555-1234
Mr. Schafer
Mr Smith
Ms Davis
Mrs. Robinson
Mr. T
'''

sentence = 'Start a sentence and then bring it to an end'

#mettre un r devant le string que l'on souhaite analyser de sorte que python n'interpetre pas differemment. Exemple: '\t' fait une tabulation naturelle en python mais r'\t' printera
# juste \t

#trouvons à présent 'abc' dans le string:

pattern = re.compile('abc')
matches = pattern.finditer(text_to_search) #renvoie un itterable de tous les match
for match in matches:
    print(match)