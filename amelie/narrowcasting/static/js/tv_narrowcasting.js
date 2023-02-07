// Constants
const SECOND = 1000
const MINUTE = 60 * SECOND
const SWAP_TIME = 20 * SECOND

// Elements
let date
let time
let activityTable
let companyAd
let news
let photo

// State
let companyBanners        = []
let selectedCompanyBanner = undefined
let activityPhotos        = []
let selectedActivity      = undefined

window.addEventListener('load', async () => {
  // Initializes the screen
  date          = document.querySelector('#date')
  time          = document.querySelector('#time')
  activityTable = document.querySelector('#activity-table')
  adContainer   = document.querySelector('.ads')
  news          = document.querySelector('.footer')
  photo         = document.querySelector('#photo')
  photoName     = document.querySelector('#photo-activity')

  // Update state
  await update(updateBannerState, 5*MINUTE)
  await update(updateActivityState, 5*MINUTE)
  await update(updateNewsState, 5*MINUTE)
  await update(updatePhotoState, 5*MINUTE)

  // Update UI
  update(updateDateTimeUI, SECOND)
  update(updateBannerUI, 20*SECOND)
  update(updatePhotoUI, 20*SECOND)
})

/*
  Helper functions
*/

const update = async (callback, interval) => {
  await callback()
  setInterval(async () => await callback(), interval)
}

const getYouTubeElement = (videoId) => {
  return `<iframe class="video" src="https://www.youtube-nocookie.com/embed/${videoId}?modestbranding=0&rel=0&showinfo=0&vq=hd1080&hl=nl&autoplay=1&controls=0&loop=1" frameborder="0" allowfullscreen></iframe>`
}

const getStreamingElement = (videoId) => {
  return `<iframe class="video" src='https://demo.openstreamingplatform.com/play/${videoId}?embedded=True&autoplay=True' height="1080" width="763"></iframe>`
}

const getImgElement = (imageId) => {
  return `<img id="adImg" src=${imageId}></img>`
}

/**
 * Do an JSON-RPC request to the backend
 * @param {string} endpoint 
 * @param {[any]} params
 */
const req = async (endpoint, params) => {
  const body = {
    jsonrpc: '2.0',
    id: 1,
    method: endpoint,
    params
  }

  return fetch('/api/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(body)
  })
    .then(res => res.json())
    .then(res => {
      if (res.error) {
        throw new Error(res.error.message)
      }

      return res.result
    })
}

/*
  Update state
*/
const updateBannerState = async () => {
  await req('getBanners', [])
    .then(banners => {
      console.log(banners)
      companyBanners = banners
    })
    .catch(console.error)
}

const updateActivityState = async () => {
  await req('getUpcomingActivities', [4, true])
    .then(updateActivityUI)
    .catch(console.error)
}

const updateNewsState = async () => {
  await req('getNews', [2, true])
    .then(updateNewsUI)
    .catch(console.error)
}

const updatePhotoState = async () => {
  await req('getLatestActivitiesWithPictures', [10])
    .then(activities => activityPhotos = activities)
    .catch(console.error)
}

/*
  Update UI elements
*/
const updateDateTimeUI = () => {
  const currentDate = new Date()

  date.textContent = currentDate.toLocaleDateString('en-GB', {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
  })
  time.textContent = currentDate.toLocaleTimeString('en-GB', {
    hour: '2-digit', minute: '2-digit', second: '2-digit'
  })
}


const updateActivityUI = (activities) => {
  if (activities.length > 0) {
    // First remove all old activities
    activityTable.textContent = ''

    const options = {
      weekday: "short", month: "short",
      day: "numeric", hour: "2-digit", minute: "2-digit"
    }

    const rows = []

    // Now generate the new table
    activities.forEach(activity => {
      const date = new Date(activity['beginDate']).toLocaleString('en-GB', options)

      const elem = `
      <tr>
        <td class="activity-icon">
          <span class="glyphicon glyphicon-calendar"></span>
        </td>
        <td class="activity-datetime">
          ${date}
        </td>
        <td class="activity-title">
          ${activity.title}
        </td>
      </tr>
      `

      rows.push(elem)
    })

    activityTable.innerHTML = rows.join('')
  } else {
      // No events on website, keep the current one and we'll check again later
  }
}

const updateNewsUI = (newsItems) => {
  // Clear old news
  news.textContent = ''

  const options = {
    weekday: "short", month: "short",
    day: "numeric"
  }

  newsItems.forEach(item => {
    const date = new Date(item["publicationDate"]).toLocaleString('nl-NL', options)
    const elem = `
    <div class="news-header">
      <span class="glyphicon glyphicon-globe"></span>
      <span>${date}</span>
      ${item.title}
    </div>
    <div class="news-content">
      ${item.introduction}
    </div>
    `
    const node = document.createElement("div")
    node.classList.add("news-item")
    node.innerHTML = elem
    news.appendChild(node)
  })

}

const updateBannerUI = () => {
  const currentIdx = companyBanners.indexOf(selectedCompanyBanner)
  const nextBanner = companyBanners[(currentIdx + 1) % companyBanners.length]

  selectedCompanyBanner = nextBanner

  console.log(nextBanner)

  adContainer.innerHTML = ''

  if (nextBanner.type === 'image') {
    adContainer.innerHTML = getImgElement(nextBanner.image)
  } else if (nextBanner.type === 'youtube') {
    adContainer.innerHTML = getYouTubeElement(nextBanner.videoId)    
  } else if (nextBanner.type === 'streamingia') {
    adContainer.innerHTML = getStreamingElement(nextBanner.videoId)
  }
}

const _setPhoto = (activity) => {
  const imageIdx = 0
  // Select the large image, and if that does not exist we select the original one
  let url = activity.images[imageIdx].large ?? activity.images[imageIdx].original

  photo.src = url
  photoName.innerText = activity.title
}

const updatePhotoUI = () => {
  // First select an activity
  const currentIdx   = activityPhotos.indexOf(selectedActivity)
  const nextActivity = activityPhotos[(currentIdx + 1) % activityPhotos.length]

  console.log('Selected activity: ', currentIdx)

  selectedActivity = nextActivity
  
  // Now, we can set the photo
  _setPhoto(nextActivity)
}