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


/**
 * Change background colors
 */
$(document).ready( function() {
    /* THEME LOADER */
    $(".theme_loader").click (function () {
    // Clear current value
    var curVal = readCookie('simple_theme');
    $("body").removeClass("simple_theme_" + curVal);

    // Udpate value
    var val = $(this).html();
    $("body").addClass("simple_theme_" + val);
    createCookie('simple_theme', val, 365);
    });
}); 

$(document).ready( function() {
    document.body.className = "simple_theme_" + readCookie("simple_theme");
});

// cookie functions http://www.quirksmode.org/js/cookies.html
function createCookie(name, value, days) {
    if (days) {
        var date = new Date();
        date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
        var expires = "; expires=" + date.toGMTString();
    }
    else var expires = "";
    document.cookie = name + "=" + value + expires + "; path=/";
}
function readCookie(name) {
    var nameEQ = name + "=";
    var ca = document.cookie.split(';');
    for(var i=0; i < ca.length; i++) {
        var c = ca[i];
        while (c.charAt(0)==' ') c = c.substring(1, c.length);
        if (c.indexOf(nameEQ) == 0) 
            return c.substring(nameEQ.length, c.length);
    }
    return null;
}
function eraseCookie(name) {
    createCookie(name, "", -1);
}
// /cookie functions