const mapDevice = obj => {
  obj._data = _.clone(obj)
  obj.switches = obj.switches || []
  return obj
}

window.app = Vue.createApp({
  el: '#vue',
  mixins: [windowMixin],
  data() {
    return {
      loading: false,
      selectedWallet: 'all',
      devices: [],
      filter: '',
      currencies: ['sat', 'EUR', 'USD', 'GBP', 'CHF', 'CAD', 'JPY', 'INR', 'ZAR', 'CZK'],
      timezones: ['Europe/Amsterdam'],
      lnurlValue: '',
      qrcodeUrl: '',
      websocketMessage: '',
      activeWebsocket: null,
      activeWebsocketDeviceId: null,
      connectedDevices: [],
      statusPollInterval: null,
      protocol: window.location.protocol,
      wsLocation: '',

      stats: {
        totalDevices: 0,
        totalSwitches: 0,
        connectedDevices: 0,
        offlineDevices: 0
      },

      deviceColumns: [
        {name: 'id', label: 'ID', field: 'id', align: 'left'},
        {name: 'title', label: 'Device', field: 'title', align: 'left', sortable: true},
        {name: 'currency', label: 'Currency', field: 'currency', align: 'left'},
        {name: 'timezone', label: 'Timezone', field: 'timezone', align: 'left'},
        {name: 'hours', label: 'Hours', align: 'left'},
        {name: 'switches', label: 'Switches', align: 'center'},
        {name: 'actions', label: '', align: 'right'}
      ],

      deviceDialog: {
        show: false,
        isEdit: false,
        data: {
          id: null,
          title: '',
          wallet: null,
          currency: 'sat',
          timezone: 'Europe/Amsterdam',
          available_start: '09:00',
          available_stop: '17:00',
          timeout: 30,
          maxperday: 0,
          closed_url: '',
          wait_url: '',
          switches: []
        }
      },

      qrCodeDialog: {
        show: false,
        data: null,
        selectedSwitch: null,
        deviceId: null
      },

      websocketDialog: {
        show: false,
        url: '',
        deviceTitle: ''
      },

      deleteDialog: {
        show: false,
        deviceId: null,
        deviceTitle: '',
        switchCount: 0
      },

      donationDialog: {
        show: false,
        address: 'u60311@blink.sv',
        message: 'DeviceTimer extension donation',
        selectedTier: null,
        customAmount: null,
        tiers: [
          {
            amount: 5000,
            label: 'Coffee',
            icon: 'local_cafe',
            description: 'Buy us a coffee or sponsor us to keep us building new extensions'
          },
          {
            amount: 50000,
            label: 'Supporter',
            icon: 'thumb_up',
            description: 'Help cover server costs and testing hardware'
          },
          {
            amount: 210000,
            label: 'Believer',
            icon: 'volunteer_activism',
            description: 'Generous support for ongoing open source development'
          },
          {
            amount: 1000000,
            label: 'Sponsor',
            icon: 'rocket_launch',
            description: 'Fund the development of a brand new extension'
          }
        ]
      },

      drawerRight: false
    }
  },

  computed: {
    wsMessage() {
      return this.websocketMessage
    },
    filteredDevices() {
      let devices = this.devices
      if (this.selectedWallet && this.selectedWallet !== 'all') {
        devices = devices.filter(d => d.wallet === this.selectedWallet)
      }
      if (this.filter) {
        const search = this.filter.toLowerCase()
        devices = devices.filter(d =>
          d.title.toLowerCase().includes(search) ||
          d.currency.toLowerCase().includes(search)
        )
      }
      return devices
    },
    walletsWithCount() {
      const wallets = this.g.user.wallets.map(w => ({
        ...w,
        deviceCount: this.devices.filter(d => d.wallet === w.id).length
      }))
      return [
        {id: 'all', name: 'All Wallets', deviceCount: this.devices.length},
        ...wallets
      ]
    }
  },

  methods: {
    onWalletChange() {
      this.calculateStats()
    },

    calculateStats() {
      let devices = this.devices
      if (this.selectedWallet && this.selectedWallet !== 'all') {
        devices = this.devices.filter(d => d.wallet === this.selectedWallet)
      }
      this.stats.totalDevices = devices.length
      this.stats.totalSwitches = devices.reduce((sum, d) => sum + (d.switches?.length || 0), 0)

      // Count connected/offline based on server-side WebSocket tracking
      const connectedIds = this.connectedDevices
      const filteredIds = devices.map(d => d.id)
      this.stats.connectedDevices = connectedIds.filter(id => filteredIds.includes(id)).length
      this.stats.offlineDevices = this.stats.totalDevices - this.stats.connectedDevices
    },

    async fetchConnectionStatus() {
      try {
        const response = await LNbits.api.request(
          'GET',
          '/devicetimer/api/v1/ws/status',
          this.g.user.wallets[0].inkey
        )
        if (response.data && response.data.connected) {
          this.connectedDevices = response.data.connected
          this.calculateStats()
        }
      } catch (err) {
        console.warn('Failed to fetch connection status')
      }
    },

    startStatusPolling() {
      // Poll every 60 seconds
      this.fetchConnectionStatus()
      this.statusPollInterval = setInterval(() => {
        this.fetchConnectionStatus()
      }, 60000)
    },

    stopStatusPolling() {
      if (this.statusPollInterval) {
        clearInterval(this.statusPollInterval)
        this.statusPollInterval = null
      }
    },

    formatHours(device) {
      return `${device.available_start} - ${device.available_stop}`
    },

    async getDevices() {
      this.loading = true
      try {
        const response = await LNbits.api.request(
          'GET',
          '/devicetimer/api/v1/device',
          this.g.user.wallets[0].adminkey
        )
        if (response.data) {
          this.devices = response.data.map(mapDevice)
          this.calculateStats()
        }
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.loading = false
      }
    },

    async createDevice() {
      const wallet = _.findWhere(this.g.user.wallets, {id: this.deviceDialog.data.wallet})
      if (!wallet) {
        this.$q.notify({type: 'warning', message: 'Please select a wallet'})
        return
      }

      const data = {...this.deviceDialog.data}
      Object.keys(data).forEach(key => {
        if (data[key] === '' || data[key] === null) {
          if (key !== 'switches') delete data[key]
        }
      })

      try {
        const response = await LNbits.api.request(
          'POST',
          '/devicetimer/api/v1/device',
          wallet.adminkey,
          data
        )
        this.devices.push(mapDevice(response.data))
        this.calculateStats()
        this.deviceDialog.show = false
        this.resetDeviceDialog()
        this.$q.notify({type: 'positive', message: 'Device created'})
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },

    async updateDevice() {
      const wallet = _.findWhere(this.g.user.wallets, {id: this.deviceDialog.data.wallet})
      if (!wallet) {
        this.$q.notify({type: 'warning', message: 'Please select a wallet'})
        return
      }

      const data = {...this.deviceDialog.data}
      Object.keys(data).forEach(key => {
        if (data[key] === '' || data[key] === null) {
          if (key !== 'switches') delete data[key]
        }
      })

      try {
        const response = await LNbits.api.request(
          'PUT',
          '/devicetimer/api/v1/device/' + data.id,
          wallet.adminkey,
          data
        )
        const index = this.devices.findIndex(d => d.id === data.id)
        if (index !== -1) {
          this.devices.splice(index, 1, mapDevice(response.data))
        }
        this.calculateStats()
        this.deviceDialog.show = false
        this.resetDeviceDialog()
        this.$q.notify({type: 'positive', message: 'Device updated'})
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },

    deleteDevice(deviceId) {
      const device = this.devices.find(d => d.id === deviceId)
      if (!device) return
      this.deleteDialog.deviceId = deviceId
      this.deleteDialog.deviceTitle = device.title
      this.deleteDialog.switchCount = device.switches?.length || 0
      this.deleteDialog.show = true
    },

    async confirmDeleteDevice() {
      const deviceId = this.deleteDialog.deviceId
      const device = this.devices.find(d => d.id === deviceId)
      try {
        const wallet = _.findWhere(this.g.user.wallets, {id: device?.wallet})
        await LNbits.api.request(
          'DELETE',
          '/devicetimer/api/v1/device/' + deviceId,
          wallet?.adminkey || this.g.user.wallets[0].adminkey
        )
        this.devices = this.devices.filter(d => d.id !== deviceId)
        this.calculateStats()
        this.deleteDialog.show = false
        this.$q.notify({type: 'positive', message: 'Device deleted'})
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },

    openDeviceDialog(device = null) {
      if (device) {
        this.deviceDialog.isEdit = true
        this.deviceDialog.data = _.clone(device._data)
      } else {
        this.deviceDialog.isEdit = false
        this.resetDeviceDialog()
      }
      this.deviceDialog.show = true
    },

    resetDeviceDialog() {
      this.deviceDialog.data = {
        id: null,
        title: '',
        wallet: this.g.user.wallets[0]?.id,
        currency: 'sat',
        timezone: 'Europe/Amsterdam',
        available_start: '09:00',
        available_stop: '17:00',
        timeout: 30,
        maxperday: 0,
        closed_url: '',
        wait_url: '',
        switches: []
      }
    },

    submitDeviceForm() {
      if (this.deviceDialog.isEdit) {
        this.updateDevice()
      } else {
        this.createDevice()
      }
    },

    openQrCodeDialog(device) {
      if (!device.switches || device.switches.length === 0) {
        this.$q.notify({type: 'warning', message: 'No switches configured'})
        return
      }
      this.qrCodeDialog.data = _.clone(device)
      this.qrCodeDialog.deviceId = device.id
      this.qrCodeDialog.selectedSwitch = device.switches[0]
      this.lnurlValue = device.switches[0].lnurl
      this.qrcodeUrl = '/devicetimer/device/' + device.id + '/' + device.switches[0].id + '/qrcode?' + Date.now()
      this.connectWebsocket(device.id)
      this.qrCodeDialog.show = true
    },

    openSwitchQrCode(device, sw) {
      if (!sw.id || !sw.lnurl) {
        this.$q.notify({type: 'warning', message: 'Save the device first to generate QR code'})
        return
      }
      this.qrCodeDialog.data = _.clone(device)
      this.qrCodeDialog.deviceId = device.id
      this.qrCodeDialog.selectedSwitch = sw
      this.lnurlValue = sw.lnurl
      this.qrcodeUrl = '/devicetimer/device/' + device.id + '/' + sw.id + '/qrcode?' + Date.now()
      this.connectWebsocket(device.id)
      this.qrCodeDialog.show = true
    },

    selectSwitch(sw) {
      this.qrCodeDialog.selectedSwitch = sw
      this.lnurlValue = sw.lnurl
      this.qrcodeUrl = '/devicetimer/device/' + this.qrCodeDialog.data.id + '/' + sw.id + '/qrcode?' + Date.now()
    },

    addSwitch() {
      if (!this.deviceDialog.data.switches) {
        this.deviceDialog.data.switches = []
      }
      this.deviceDialog.data.switches.push({
        amount: 10,
        gpio_pin: 21,
        gpio_duration: 2100,
        label: `Switch ${this.deviceDialog.data.switches.length + 1}`
      })
    },

    removeSwitch(index) {
      this.deviceDialog.data.switches.splice(index, 1)
    },

    connectWebsocket(deviceId) {
      this.disconnectWebsocket()

      if (!('WebSocket' in window)) {
        this.websocketMessage = 'WebSocket not supported'
        return
      }

      // Use extension WebSocket endpoint with browser type (doesn't count as hardware connection)
      const websocketUrl = this.wsLocation + '/devicetimer/api/v1/ws/' + deviceId + '?type=browser'
      this.websocketMessage = 'Connecting...'
      this.activeWebsocketDeviceId = deviceId

      try {
        const ws = new WebSocket(websocketUrl)
        this.activeWebsocket = ws

        ws.onopen = () => {
          this.websocketMessage = 'Connected'
        }

        ws.onmessage = (event) => {
          this.websocketMessage = 'Payment received!'
          // Refresh status after payment
          setTimeout(() => this.fetchConnectionStatus(), 1000)
        }

        ws.onclose = () => {
          this.websocketMessage = ''
          if (this.activeWebsocket === ws) {
            this.activeWebsocket = null
            this.activeWebsocketDeviceId = null
          }
        }

        ws.onerror = () => {
          this.websocketMessage = 'Connection error'
          if (this.activeWebsocket === ws) {
            this.activeWebsocket = null
            this.activeWebsocketDeviceId = null
          }
        }
      } catch (e) {
        this.websocketMessage = 'WebSocket error'
        this.activeWebsocketDeviceId = null
      }
    },

    disconnectWebsocket() {
      if (this.activeWebsocket) {
        this.activeWebsocket.close()
        this.activeWebsocket = null
        this.activeWebsocketDeviceId = null
        this.websocketMessage = ''
      }
    },

    closeQrCodeDialog() {
      this.qrCodeDialog.show = false
      this.disconnectWebsocket()
    },

    copyText(text, message = 'Copied!') {
      Quasar.copyToClipboard(text).then(() => {
        this.$q.notify({type: 'positive', message})
      })
    },

    openWebsocketDialog(device) {
      // Show extension WebSocket URL for hardware configuration
      this.websocketDialog.url = this.wsLocation + '/devicetimer/api/v1/ws/' + device.id
      this.websocketDialog.deviceTitle = device.title
      this.websocketDialog.show = true
    },

    exportCSV() {
      LNbits.utils.exportCSV(this.deviceColumns, this.devices)
    },

    openDocumentation() {
      window.open('https://github.com/DoktorShift/DeviceTimer', '_blank')
    },

    openDonationDialog() {
      this.donationDialog.selectedTier = this.donationDialog.tiers[0]
      this.donationDialog.customAmount = null
      this.donationDialog.show = true
    },

    selectDonationTier(tier) {
      this.donationDialog.selectedTier = tier
      this.donationDialog.customAmount = null
    },

    selectCustomAmount() {
      this.donationDialog.selectedTier = null
    },

    getDonationAmount() {
      if (this.donationDialog.selectedTier) {
        return this.donationDialog.selectedTier.amount
      }
      return this.donationDialog.customAmount || 0
    },

    getDonationQrUrl() {
      const amount = this.getDonationAmount()
      const address = this.donationDialog.address
      if (amount > 0) {
        return 'https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=' +
          encodeURIComponent('lightning:' + address + '?amount=' + (amount * 1000))
      }
      return 'https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=' +
        encodeURIComponent('lightning:' + address)
    },

    formatSats(amount) {
      if (amount >= 1000000) {
        return (amount / 1000000).toFixed(1).replace(/\.0$/, '') + 'M'
      }
      if (amount >= 1000) {
        return (amount / 1000).toFixed(0) + 'k'
      }
      return amount.toString()
    },

    isDeviceConnected(deviceId) {
      return this.connectedDevices.includes(deviceId)
    }
  },

  async created() {
    this.selectedWallet = 'all'
    this.wsLocation = (window.location.protocol === 'https:' ? 'wss://' : 'ws://') + window.location.host

    await this.getDevices()
    this.startStatusPolling()

    try {
      const response = await LNbits.api.request('GET', '/devicetimer/api/v1/timezones')
      this.timezones = response.data
    } catch (err) {
      console.warn('Failed to load timezones')
    }
  },

  beforeUnmount() {
    this.stopStatusPolling()
    this.disconnectWebsocket()
  }
})
