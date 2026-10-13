import {copyFileSync,mkdirSync} from 'node:fs';
mkdirSync('openapi',{recursive:true});
copyFileSync('../backend/openapi/openapi.json','openapi/openapi.json');
