$(document).ready(function(e) {
    $(".media_links").each(function(index, gal){
        $(this).find(".thumb").colorbox({
            rel: gal,
            maxWidth:"80%",
            maxHeight:"80%",
            scalePhotos:true,
        })
    });
});
