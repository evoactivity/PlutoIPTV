const fs = require('fs');

function lookupSlugs(favoriteSlugsFilePath){
    if(!fs.existsSync(favoriteSlugsFilePath)) {
        return [];
    }
    return fs.readFileSync(favoriteSlugsFilePath,{encoding:'utf8', flag:'r'}).split("\n").map(l=>l.trim()).filter(l=>!l.startsWith("#")&&l.length > 0);
}

class FavoritesFilter extends Function {
    
    constructor(favoriteSlugs) {
      super('return arguments.callee._call.apply(arguments.callee, arguments)')
      this._favoriteSlugs = favoriteSlugs;
      this._tracker = {};
      this._channelCount = 0;
      favoriteSlugs.forEach(s=>this._tracker[s]=0);
    }
    
    isEmpty() {
        return this._favoriteSlugs.length === 0;
    }

    _call(channel) {
        this._channelCount += 1;
        const slug = channel.slug;
        if(this._tracker[slug]!=null){
            this._tracker[slug]+=1;
            return true;
        } else {
            return false;
        }
    }

    printSummary(){
        const unusedFavoriteSlugs = this.unusedFavoriteSlugs();
        const filtersUsed = this._favoriteSlugs.length - unusedFavoriteSlugs.length;
        console.log(`[INFO] Filter Returned ${filtersUsed}/${this._channelCount} channels`);
        if(unusedFavoriteSlugs.length >0) {
            console.warn('[WARN] Unknown Favorite Slugs:', unusedFavoriteSlugs)
        }
    }

    unusedFavoriteSlugs() {
        return this._favoriteSlugs.filter(s=>this._tracker[s]===0);
    }
  }

const favorites = {

    from(favoriteSlugsFilePath) {
        const favoriteSlugs = lookupSlugs(favoriteSlugsFilePath);
        return new FavoritesFilter(favoriteSlugs);
    }
};


module.exports = favorites;