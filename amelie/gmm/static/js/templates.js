/*
 Copyright (c) 2003-2015, CKSource - Frederico Knabben. All rights reserved.
 For licensing, see LICENSE.md or https://ckeditor.com/license
 */
CKEDITOR.addTemplates("default", {
    templates: [{
        title: "ALV",
        description: "Template voor ALVs",
        html:
            '<ol>' +
                '<li>Opening</li>' +
                '<li>Mededelingen' +
                '<ol start="1" style="list-style-type: lower-alpha;">' +
                    '<li>Van het bestuur</li>' +
                    '<li>Van andere aanwezigen</li>' +
                '</ol>' +
                '</li>' +
                '<li><a href="">Vaststellen agenda</a></li>' +
                '<li>Secretarieel' +
                '<ol start="1" style="list-style-type: lower-alpha;">' +
                    '<li><a href="">Notulen ALV xx xx xxxx</a>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<em>(ter goedkeuring)</em></li>' +
                    '<li>Binnengekomen stukken' +
                    '<ol start="1" style="list-style-type: lower-roman;">' +
                        '<li><a href="">xxx</a></li>' +
                    '</ol>' +
                    '</li>' +
                    '<li><a href="">Actiepunten</a>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<em>(ter informatie)</em></li>' +
                '</ol>' +
                '</li>' +
                '<li><a href="">xxx</a>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<em>(ter goedkeuring)</em></li>' +
                '<li><a href="">xxx</a>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<em>(ter informatie)</em></li>' +
                '<ol start="1" style="list-style-type: lower-alpha;">' +
                    '<li>x</li>' +
                '</ol>' +
                '</li>' +
                '<li>Wat verder ter tafel komt</li>' +
                '<li>Rondvraag</li>' +
                '<li>Sluiting</li>' +
            '</ol>' +
            '<p></p>'

    }, {
        title: "Erata",
        description: "Template voor Erata",
        html:             '<h3>Errata</h3>' +
            '<ul>' +
                '<li><a href="">xxx</a></li>' +
            '</ul>'
    }]
});
