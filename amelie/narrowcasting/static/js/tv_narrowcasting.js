// Constants
const SECOND = 1000
const MINUTE = 60 * SECOND
const SWAP_TIME = 20 * SECOND

// Elements
let date
let time
let activityTable

window.addEventListener('load', () => {
  // Initializes the screen
  date          = document.querySelector('#date')
  time          = document.querySelector('#time')
  activityTable = document.querySelector('#activity-table')

  // Update state
  update(updateBannerState, 5*MINUTE)
  update(updateActivityState, 5*MINUTE)

  // Update UI
  update(updateDateTimeUI, SECOND)
})

/*
  Helper functions
*/

const update = (callback, interval) => {
  callback()
  setInterval(callback, interval)
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
const updateBannerState = () => {
  req('getBanners', [])
    .then(updateBannerUI)
    .catch(console.error)
}

const updateActivityState = () => {
  req('getUpcomingActivities', [4])
    .then(updateActivityUI)
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

const updateBannerUI = (banners) => {
  console.log(banners)
}