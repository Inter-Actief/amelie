import os

#
# Create a LESS file for all files in the folder, in which the reference to that file
# is mentioned as an icon-FILENAME and icon-list-FILENAME
#

print('@PATH: "../";')

for file in os.listdir("."):
    basename = os.path.splitext(file)[0]
    print('.icon-%s { background: transparent url("@{PATH}img/icons/%s") no-repeat; }' % (basename, file))
    print('.icon-list-%s { list-style-image: url("@{PATH}img/icons/%s"); }' % (basename, file))
