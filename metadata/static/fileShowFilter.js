(function ($) {
    // custom css expression for a case-insensitive contains()
    jQuery.expr[':'].Contains = function(a,i,m) {
        return (a.textContent || a.innerText || "").toUpperCase().indexOf(m[3].toUpperCase())>=0;
    };

function listFilter(header, list) {
// adapted from Kilian Valkhof
    var form = $("<form>").attr({"class":"filterform", "action":"#"}),
        input = $("<input>").attr({"class":"filterinput","type":"text"});
    
    $(form).append(input).appendTo(header);

    $(input).change( function () {
        var filter = $(this).val(); // get input value
        if (filter) {
            $(list).find("option:not(:Contains(" + filter + "))").hide();
            $(list).find("option:Contains(" + filter + ")").show();
        } else {
        $(list).find("option").show();
        }

    }).keyup( function () {
        // change event runs after every key
        $(this).change();
    });

}


$(function () {
    listFilter($("#fileheader"), $("#filelist"));
});
}(jQuery));
