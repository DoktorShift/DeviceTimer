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
      selectedWallet: null,
      devices: [],
      filter: '',
      currencies: ['sat', 'EUR', 'USD', 'GBP', 'CHF', 'CAD', 'JPY', 'INR', 'ZAR', 'CZK'],
      timezones: ['Europe/Amsterdam'],
      lnurlValue: '',
      qrcodeUrl: '',
      websocketMessage: '',
      protocol: window.location.protocol,
      wsLocation: '',

      stats: {
        totalDevices: 0,
        activeDevices: 0,
        totalSwitches: 0
      },

      deviceColumns: [
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
        selectedSwitch: null
      },

      drawerRight: false
    }
  },

  computed: {
    wsMessage() {
      return this.websocketMessage
    },
    filteredDevices() {
      if (!this.filter) return this.devices
      const search = this.filter.toLowerCase()
      return this.devices.filter(d =>
        d.title.toLowerCase().includes(search) ||
        d.currency.toLowerCase().includes(search)
      )
    },
    walletsWithCount() {
      return this.g.user.wallets.map(w => ({
        ...w,
        deviceCount: this.devices.filter(d => d.wallet === w.id).length
      }))
    }
  },

  methods: {
    onWalletChange() {
      this.getDevices()
    },

    calculateStats() {
      this.stats.totalDevices = this.devices.length
      this.stats.activeDevices = this.devices.length
      this.stats.totalSwitches = this.devices.reduce((sum, d) => sum + (d.switches?.length || 0), 0)
    },

    formatHours(device) {
      return `${device.available_start} - ${device.available_stop}`
    },

    async getDevices() {
      this.loading = true
      try {
        const wallet = _.findWhere(this.g.user.wallets, {id: this.selectedWallet})
        const response = await LNbits.api.request(
          'GET',
          '/devicetimer/api/v1/device',
          wallet?.adminkey || this.g.user.wallets[0].adminkey
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
      LNbits.utils
        .confirmDialog(`Delete "${device?.title}"?`)
        .onOk(async () => {
          try {
            const wallet = _.findWhere(this.g.user.wallets, {id: device.wallet})
            await LNbits.api.request(
              'DELETE',
              '/devicetimer/api/v1/device/' + deviceId,
              wallet?.adminkey || this.g.user.wallets[0].adminkey
            )
            this.devices = this.devices.filter(d => d.id !== deviceId)
            this.calculateStats()
            this.$q.notify({type: 'positive', message: 'Device deleted'})
          } catch (error) {
            LNbits.utils.notifyApiError(error)
          }
        })
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
      this.qrCodeDialog.selectedSwitch = device.switches[0]
      this.lnurlValue = device.switches[0].lnurl
      this.qrcodeUrl = '/devicetimer/device/' + device.id + '/' + device.switches[0].id + '/qrcode?' + Date.now()
      this.websocketConnector(this.wsLocation + '/api/v1/ws/' + device.id)
      this.qrCodeDialog.show = true
    },

    openSwitchQrCode(device, sw) {
      if (!sw.id || !sw.lnurl) {
        this.$q.notify({type: 'warning', message: 'Save the device first to generate QR code'})
        return
      }
      this.qrCodeDialog.data = _.clone(device)
      this.qrCodeDialog.selectedSwitch = sw
      this.lnurlValue = sw.lnurl
      this.qrcodeUrl = '/devicetimer/device/' + device.id + '/' + sw.id + '/qrcode?' + Date.now()
      this.websocketConnector(this.wsLocation + '/api/v1/ws/' + device.id)
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

    websocketConnector(websocketUrl) {
      if (!('WebSocket' in window)) {
        this.websocketMessage = 'WebSocket not supported'
        return
      }
      try {
        this.websocketMessage = 'Connecting...'
        const ws = new WebSocket(websocketUrl)
        ws.onopen = () => {
          this.websocketMessage = 'connected'
        }
        ws.onmessage = evt => {
          this.websocketMessage = 'Payment received!'
        }
        ws.onclose = () => {
          this.websocketMessage = 'Disconnected'
        }
        ws.onerror = () => {
          this.websocketMessage = 'Connection error'
        }
      } catch (e) {
        this.websocketMessage = 'WebSocket error'
      }
    },

    copyText(text, message = 'Copied!') {
      Quasar.copyToClipboard(text).then(() => {
        this.$q.notify({type: 'positive', message})
      })
    },

    copyWebsocketUrl(deviceId) {
      const url = this.wsLocation + '/api/v1/ws/' + deviceId
      this.copyText(url, 'WebSocket URL copied')
    },

    exportCSV() {
      LNbits.utils.exportCSV(this.deviceColumns, this.devices)
    },

    openDocumentation() {
      window.open('https://github.com/DoktorShift/DeviceTimer', '_blank')
    }
  },

  async created() {
    this.selectedWallet = this.g.user.wallets[0]?.id
    this.wsLocation = (window.location.protocol === 'https:' ? 'wss://' : 'ws://') + window.location.host

    await this.getDevices()

    try {
      const response = await LNbits.api.request('GET', '/devicetimer/api/v1/timezones')
      this.timezones = response.data
    } catch (err) {
      console.warn('Failed to load timezones')
    }
  }
})
