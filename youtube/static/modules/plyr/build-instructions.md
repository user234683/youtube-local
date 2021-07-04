# Build steps for Plyr (3.6.8)

Tested on Debian.

First install yarn (Javascript package manager). Instructions [here](https://classic.yarnpkg.com/en/docs/install/).

Clone the repo to a location of your choosing:
```
git clone https://github.com/sampotts/plyr.git
cd plyr
```

Install Plyr's dependencies:
```
yarn install
```

Build with gulp (which was hopefully installed by yarn):
```
gulp build
```

plyr.js and other files will be in the `dist` directory.
