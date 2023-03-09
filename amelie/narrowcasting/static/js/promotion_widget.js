function PromotionWidget() {
    Widget.call(this);

    this.television_promotions = [];
    this.current_promotion = null;
    this.current_idx = 0;
    this.ticks = 0;
    this.duration = 0;
}

PromotionWidget.prototype = new Widget();

PromotionWidget.prototype.constructor = PromotionWidget;

PromotionWidget.prototype.pre_focus = function () {
    var self = this;
    $.jsonRPC.request('getTelevisionPromotions', {
        params: [],
        success: function(result) {
            self.television_promotions = result.result;
            self.duration = result.result.length > 0 ? 20 : 0;
        },
        error: function(result) {
            self.duration = 0;
            console.log("Could not load television promotions");
        }
    });
};

PromotionWidget.prototype.get_duration = function () { return this.duration };

PromotionWidget.prototype.tick = function () {
    if(this.ticks == 0 || !this.photo_showing) this.change_photo();

    this.ticks = (this.ticks + 1) % this.get_duration();
};

PromotionWidget.prototype.change_photo = function () {
    if (this.television_promotions.length > 0){

        if (this.current_idx >= 0) {
            var idx = (this.current_idx + 1) % this.television_promotions.length;

            this.current_promotion = this.television_promotions[idx];
            this.current_idx = idx;
        } else if (this.television_promotions.length > 0) {
            this.current_promotion = this.television_promotions[0];
            this.current_idx = 0;
        }

        var photo_url = this.current_promotion.image;

        var self = this;

        $('<img />').attr({
		    src: photo_url,
            id: "photo"
        }).load(function(){
            $(".photo-wrapper #photo").remove();
            $(".photo-wrapper").append($(this));

            // if(self.current_promotion.title != undefined){
            //     $("#photo-activity").html(self.current_promotion.title);        
            // } else {
            //     // This is a hack, hiding and showing does not yet work correctly
            //     $("#photo-activity").html("Promotion");
            // }

            $("#photo-activity").hide();
            
            if($(this).height() > $(this).width()){
                $("#photo").addClass("portrait");
            }

            self.photo_showing = true;
        });
    } else {
        self.photo_showing = false;
    }
};

// PromotionWidget.prototype.get_duration = function () { return this.duration; };
PromotionWidget.prototype.get_duration = function () { return 5; };
