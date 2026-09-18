import { http } from './client.js';

const RESOURCE = '/septic';

export const septicApi = {
  overview: () => http.get(`${RESOURCE}/overview`),
  schedules: (params) => http.get(`${RESOURCE}/schedules`, params),
  list: (params) => http.get(`${RESOURCE}/cleanings`, params),
  detail: (id) => http.get(`${RESOURCE}/cleanings/${id}`),
  create: (payload) => http.post(`${RESOURCE}/cleanings`, payload),
  update: (id, payload) => http.patch(`${RESOURCE}/cleanings/${id}`, payload),
  remove: (id) => http.delete(`${RESOURCE}/cleanings/${id}`),
};
