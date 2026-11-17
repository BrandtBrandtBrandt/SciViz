import {build} from 'esbuild';
import {cp,mkdir,copyFile,writeFile,rm} from 'node:fs/promises';
await rm('dist',{recursive:true,force:true});
await mkdir('dist/assets',{recursive:true});
await cp('public','dist/assets',{recursive:true});
await copyFile('index.html','dist/index.html');
await build({entryPoints:['src/app.ts'],outdir:'dist/assets',bundle:true,splitting:true,format:'esm',target:'es2022',minify:true,legalComments:'linked'});
await copyFile('node_modules/@gradio/client/LICENSE','dist/assets/gradio-client-LICENSE.txt');
await writeFile('dist/assets/NOTICE.txt',`SciViz integration, visual direction and interface by Matias Brandt Møller.
Gradio JavaScript client 2.7.2: https://github.com/gradio-app/gradio
The package ships an Apache-2.0 LICENSE file (retained); its package metadata says ISC.
Backend models and rendering credits: https://huggingface.co/spaces/BrandtBrandtBrandt/sciviz
No model weights are included in this frontend.
`);
console.log('Built standalone SciViz frontend in web/dist.');
