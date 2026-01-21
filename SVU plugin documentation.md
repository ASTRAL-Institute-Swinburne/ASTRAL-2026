---
tags:
  - documentation
  - 2026/01/21
---

#### How to make a script suitable for SVU:
1. the script needs its output to be a jpg
	this is what SVU will display to the screen once the script has run
2. have the main function return the jpg's filename at the end of running the program
	this signals the program has stopped running & tells SVU what name to display
3. when saving your data as a jpg, join the filename with the variable {{DATA_PATH}} to create its path
	SVU will substitute your library location into {{DATA_PATH}} so the image will save in the correct place within its system
		e.g. ```img.save({{DATA_PATH}} + 'example_name.jpg')```

#### How to add plugin into SVU:
1. go into settings panel of SVU
2. go into the library tab
3. ensure user library location is defined (i.e. there is a path at the top)
4. add python script to library using '+' symbol
5. add in metadata for the script, including a thumbnail

#### How to run plugin in SVU:
1. if plugin name is not known, say 'show me plugins'
2. say 'run {name of plugin}' 


links: [[ASTRAL MOC]], [[SVU index]], [[Millipede index]]


