import fs from 'node:fs'
import path from 'node:path'
import tus from 'tus-js-client'

const supabaseUrl = process.env.VITE_SUPABASE_URL
const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY
const bucket = process.env.SUPABASE_BUCKET || 'movies'
const folder = process.env.SUPABASE_MOVIES_PREFIX || ''

if (!supabaseUrl) {
  console.error('Missing VITE_SUPABASE_URL in local environment variables.')
  process.exit(1)
}

if (!serviceRoleKey) {
  console.error('Missing SUPABASE_SERVICE_ROLE_KEY in local environment variables.')
  process.exit(1)
}

const files = process.argv.slice(2)

if (files.length === 0) {
  console.error('Usage: npm run upload:movies -- <absolute-or-relative-file-path> [more files]')
  process.exit(1)
}

const resumableEndpoint = `${supabaseUrl.replace(/\/$/, '')}/storage/v1/upload/resumable`

function getContentType(fileName) {
  const ext = path.extname(fileName).toLowerCase()
  if (ext === '.webm') return 'video/webm'
  if (ext === '.mov') return 'video/quicktime'
  if (ext === '.mp4') return 'video/mp4'
  return 'application/octet-stream'
}

function toPublicUrl(objectPath) {
  const encodedPath = objectPath.split('/').map(encodeURIComponent).join('/')
  return `${supabaseUrl.replace(/\/$/, '')}/storage/v1/object/public/${bucket}/${encodedPath}`
}

function uploadOne(filePath) {
  return new Promise((resolve, reject) => {
    const resolved = path.resolve(filePath)

    if (!fs.existsSync(resolved)) {
      reject(new Error(`File does not exist: ${resolved}`))
      return
    }

    const stats = fs.statSync(resolved)
    const objectName = `${folder}${folder && !folder.endsWith('/') ? '/' : ''}${path.basename(resolved)}`
    const stream = fs.createReadStream(resolved)

    const upload = new tus.Upload(stream, {
      endpoint: resumableEndpoint,
      uploadSize: stats.size,
      retryDelays: [0, 1500, 3000, 5000, 10000],
      headers: {
        authorization: `Bearer ${serviceRoleKey}`,
        'x-upsert': 'true',
      },
      metadata: {
        bucketName: bucket,
        objectName,
        contentType: getContentType(resolved),
      },
      onProgress(bytesUploaded, bytesTotal) {
        const pct = ((bytesUploaded / bytesTotal) * 100).toFixed(2)
        process.stdout.write(`\rUploading ${path.basename(resolved)}: ${pct}%`)
      },
      onError(error) {
        process.stdout.write('\n')
        reject(error)
      },
      onSuccess() {
        process.stdout.write('\n')
        console.log(`Uploaded ${path.basename(resolved)} to ${bucket}/${objectName}`)
        console.log(`Public URL: ${toPublicUrl(objectName)}`)
        resolve(undefined)
      },
    })

    upload
      .findPreviousUploads()
      .then((previousUploads) => {
        if (previousUploads.length > 0) upload.resumeFromPreviousUpload(previousUploads[0])
        upload.start()
      })
      .catch(reject)
  })
}

for (const filePath of files) {
  try {
    await uploadOne(filePath)
  } catch (error) {
    console.error(`Upload failed for ${filePath}:`, error)
    process.exit(1)
  }
}

console.log('All uploads completed.')
