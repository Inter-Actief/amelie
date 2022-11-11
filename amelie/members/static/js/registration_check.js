/*
 * Based on Juliana by Cas Ebbers <cjaebbers@gmail.com>
 */

/*
 * NFC SCAN
 */
Scanner = {
    init: function () {
        var scanner = this;
        var socket;

        // JulianaNFC_C application on Windows will not connect without nfc protocol
        socket = new WebSocket('ws://localhost:3000', 'nfc');

        socket.onmessage = function (event) {
            var rfid = JSON.parse(event.data);
            scanner.action(rfid);
        }

    },
    action: function (rfid) {
        /*
        Type identifier	ATQA	SAK
        02	            00:04	08
        03	            00:02	18
        04	            03:44	20
        05	            00:44	00
        */

        var typeIdentifier = 'xx';

        if(rfid['atqa']== '00:04' && rfid['sak'] == '08') {
            typeIdentifier = '02';
        } else if(rfid['atqa']== '00:02' && rfid['sak'] == '18') {
            typeIdentifier = '03';
        } else if(rfid['atqa']== '03:44' && rfid['sak'] == '20') {
            typeIdentifier = '04';
        } else if(rfid['atqa']== '00:44' && rfid['sak'] == '00') {
            typeIdentifier = '05';
        } else {
            alert('RFID niet herkend');
            return;
        }

        $('#id_code').val(typeIdentifier + ',' + rfid['uid']);
        $('#enrollment_control_form').submit();
    }
};

$(function () {
    Scanner.init();
    $('#id_student_number').focus();
});
