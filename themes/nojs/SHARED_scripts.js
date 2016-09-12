/**
 * Load page where link in given element id points.
 */
function gotopage(divid) {
    var div = $('#' + divid);
    if (div) {
        var link = div.children('a')[0];
        if (link) {
            document.location = link;
        }
    }
}

$(document).keypress(function(e) {
    switch(e.keyCode) {
        case 37: /* Left */
            gotopage('prev_link');
            break;
        case 38: /* Up */
            gotopage('index_link');
            break;
        case 39: /* Right */
        case 13: /* Enter */
        case 32: /* Space */
            gotopage('next_link');
            break;
      }
});

