# Build steps for Plyr (3.6.8)

Tested on Hyperbola GNU with Linux-libre.

First install npm (node package manager).

Clone the repo to a location of your choosing:
```
git clone https://github.com/sampotts/plyr.git
cd plyr
```

Install Plyr's dependencies:
```
npm install
```

Build with npm:
```
npm run build
```

plyr.js and other files will be in the `dist` directory.
