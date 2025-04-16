mkdir test_peers
mkdir test_peers\seeder
mkdir test_peers\leecher3
mkdir test_peers\leecher4
mkdir test_peers\leecher5
copy *.py test_peers\seeder
copy *.py test_peers\leecher3
copy *.py test_peers\leecher4
copy *.py test_peers\leecher5
copy testing.torrent test_peers\seeder
copy testing.torrent test_peers\leecher3
copy testing.torrent test_peers\leecher4
copy testing.torrent test_peers\leecher5
start cmd /k "cd test_peers\seeder && python ui.py"
start cmd /k "cd test_peers\leecher3 && python ui.py"
start cmd /k "cd test_peers\leecher4 && python ui.py"
start cmd /k "cd test_peers\leecher5 && python ui.py"