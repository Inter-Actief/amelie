/*
 * RFID card interface by Kevin Alberts <kevin@kevinalberts.nl>
 *     Based on Juliana, by Cas Ebbers <cjaebbers@gmail.com>, from Alexia.
 *     For use in Amelie, the Inter-/Actief/ website, to
 *     register RFID cards to accounts using the same
 *     RFID-reader as in the drink rooms.
 */

_pad = function (n, c) {
    n = n.toString();
    return n.length < c ? _pad('0' + n, c, '0') : n;
};

// Function to go from ATQA/SAK to RFID identifier.
rfid_to_identifier = function(rfid) {
    var ia_rfid_prefix = "";

    if (!(rfid.hasOwnProperty("atqa") && rfid.hasOwnProperty("sak") && rfid.hasOwnProperty("uid"))){
        throw 'invalid rfid object'
    }

    if (rfid['atqa'] === "00:04" && rfid['sak'] === "08") {
        // MIFARE Classic 1k
        ia_rfid_prefix = '02';
    } else if (rfid['atqa'] === "00:02" && rfid['sak'] === "18") {
        // MIFARE Classic 4k
        ia_rfid_prefix = '03'
    } else if (rfid['atqa'] === "03:44" && rfid['sak'] === "20") {
        // MIFARE DESFire
        ia_rfid_prefix = '04'
    } else if (rfid['atqa'] === "00:44" && rfid['sak'] === "00") {
        // MIFARE Ultralight
        ia_rfid_prefix = '05'
    } else {
        throw 'atqa/sak combination unknown';
    }
    return ia_rfid_prefix+","+rfid['uid'];
};

sumbit_form = function(tag) {
    $('#rfid-form-tag').attr('value', tag);
    $('#rfid-form').submit();
};

/*
 * NFC SCAN
 */
Scanner = {
    init: function () {
        var socket;

        // JulianaNFC_C application on Windows will not connect without nfc protocol
        socket = new WebSocket('ws://localhost:3000', 'nfc');

        socket.onopen = Settings.onopen;

        socket.onerror = Settings.onerror;

        socket.onmessage = Settings.onmessage;

    },
    action: Settings.action
};

/*
 * DISPLAY - upper status line
 */
Display = {
    set: function (text) {
        $('#display').html(text);
    }
};

$(function () {
    Scanner.init();
});
