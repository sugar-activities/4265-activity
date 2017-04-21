# -*- coding: iso-8859-1 -*-
# Copyright (C) 2006 by Martin Sevior
# Copyright (C) 2006-2007 Marc Maurer <uwog@uwog.net>
# Copyright (C) 2007, One Laptop Per Child
# Copyright (C) 2009 Plan Ceibal <comunidad@plan.ceibal.edu.uy>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

from gettext import gettext as _
import logging
import time
import shutil

import pygtk
pygtk.require('2.0')
import sys, os, errno
import pango

import dbus
import gtk
import telepathy
import telepathy.client

from sugar.activity.activity import Activity, ActivityToolbox, EditToolbar
from sugar.presence import presenceservice

from abiword import Canvas
import toolbar
from toolbar import WriteActivityToolbarExtension, WriteEditToolbar, TextToolbar, ImageToolbar, TableToolbar, FormatToolbar, ViewToolbar
from sugar.activity.activity import get_bundle_path

import threading
from Xlib import X, display
import ConfigParser

from sugar.graphics.icon import Icon
from sugar.graphics.toolbutton import ToolButton
from sugar.graphics.toggletoolbutton import ToggleToolButton
from sugar.graphics.combobox import ComboBox
from sugar.graphics.toolcombobox import ToolComboBox
from sugar.graphics.objectchooser import ObjectChooser
from sugar.graphics import iconentry
from sugar.activity.activity import ActivityToolbar
from sugar.activity.activity import EditToolbar
from sugar.graphics.menuitem import MenuItem

logger = logging.getLogger('write-activity')

#gtk.gdk.threads_init()
import gobject
gobject.threads_init()

velocidades = {'lenta': 2.5, 'media': 2.0, 'rapida':1.5}

PATH_CONFIG_BARRIDO = 'barrido.conf'

class AbiWordActivity (Activity):
    MAYUSCULA = True;
    BOTONESxBARRIDO = False;
    BOTONESxBARRIDO_MENU = False;	
    BOTONESxBARRIDO_MENU_ITEM = False;
    BOTONESxBARRIDOxFILA = False;
    losBotones = []
    btn_actual = None;
    fila_actual = None;
    fila_actual_nro = -1;
    menu_item_actual = None;
    fila_1 = [];
    fila_2 = [];
    fila_3 = [];
    fila_4 = [];
    fila_5 = [];
    fila_6 = [];
    t_inicial = 0;
    t_final = 0;
    def __init__ (self, handle):
        Activity.__init__ (self, handle)

        # abiword uses the current directory for all its file dialogs 
        os.chdir(os.path.expanduser('~'))

        # create our main abiword canvas
        self.abiword_canvas = Canvas()
        self.abiword_canvas.connect('text-selected', self._selection_cb)
        self.abiword_canvas.connect('image-selected', self._selection_cb)
        self.abiword_canvas.connect('selection-cleared', self._selection_cleared_cb)


    ########################################################################

	self.box = gtk.VBox()
	self.box.show()

	self.mi_teclado = self.mostrar_teclado()
	self.mi_teclado.show_all()

	self.abiword_canvas.connect_after('map-event', self._map_event_cb)
	self.abiword_canvas.show()

	self.event_box = gtk.EventBox()

	box_interno = gtk.VBox()
	box_interno.add(self.mi_teclado)
	box_interno.add(self.abiword_canvas)
	box_interno.show()

	self.event_box.add(box_interno)
	self.event_box.set_events(gtk.gdk.BUTTON_PRESS)
	self.event_box.show()

	self.box.add(self.event_box)

	self.ebc = self.event_box.connect("button_press_event", self.mouse_boton)

        self.set_canvas(self.box)

    ########################################################################
        
        # create our toolbars
        self.toolbox = ActivityToolbox(self)
        self.set_toolbox(self.toolbox)
        self.toolbox.show()

        activity_toolbar_ext = WriteActivityToolbarExtension(self, self.toolbox, self.abiword_canvas, self)

        self.text_toolbar = TextToolbar(self.toolbox, self.abiword_canvas, self)

        self._edit_toolbar = WriteEditToolbar(self.toolbox, self.abiword_canvas, self.text_toolbar, self)
        self.toolbox.add_toolbar(_('Edit'), self._edit_toolbar)
        self._edit_toolbar.show()

        self.toolbox.add_toolbar(_('Text'), self.text_toolbar)
        self.text_toolbar.show()

        self.image_toolbar = ImageToolbar(self.toolbox, self.abiword_canvas, self)
        self.toolbox.add_toolbar(_('Image'), self.image_toolbar)
        self.image_toolbar.show()

        self.table_toolbar = TableToolbar(self.toolbox, self.abiword_canvas, self)
        self.toolbox.add_toolbar(_('Table'), self.table_toolbar)
        self.table_toolbar.show()

        self.format_toolbar = FormatToolbar(self.toolbox, self.abiword_canvas, self)
        self.toolbox.add_toolbar(_('Format'), self.format_toolbar)
        self.format_toolbar.show()

        self.view_toolbar = ViewToolbar(self.abiword_canvas, self.mi_teclado, self)
        self.toolbox.add_toolbar(_('View'), self.view_toolbar)
        self.view_toolbar.show()

        # the text toolbar should be our default toolbar
        self.toolbox.set_current_toolbar(toolbar.TOOLBAR_TEXT)

    ########################################################################

    def _map_event_cb(self, event, activity):
        logger.debug('_map_event_cb')
    
        # set custom keybindings for Write
        logger.debug("Loading keybindings")
        keybindings_file = os.path.join( get_bundle_path(), "keybindings.xml" )
        self.abiword_canvas.invoke_cmd('com.abisource.abiword.loadbindings.fromURI', keybindings_file, 0, 0)

        # no ugly borders please
        self.abiword_canvas.set_property("shadow-type", gtk.SHADOW_NONE)

        # we only do per-word selections (when using the mouse)
        self.abiword_canvas.set_word_selections(True)

        # we want a nice border so we can select paragraphs easily
        self.abiword_canvas.set_show_margin(True)

        # activity sharing
        self.participants = {}
        pservice = presenceservice.get_instance()

        bus = dbus.Bus()
        name, path = pservice.get_preferred_connection()
        self.conn = telepathy.client.Connection(name, path)
        self.initiating = None
        self.joined = False

        self.connect('shared', self._shared_cb)

        if self._shared_activity:
            # we are joining the activity
            logger.debug("We are joining an activity")
            self.connect('joined', self._joined_cb)
            self._shared_activity.connect('buddy-joined', self._buddy_joined_cb)
            self._shared_activity.connect('buddy-left', self._buddy_left_cb)
            if self.get_shared():
#                # oh, OK, we've already joined
                self._joined_cb()
        else:
            # we are creating the activity
            logger.debug("We are creating an activity")

        owner = pservice.get_owner()

	#tamaño por defecto:
	self.abiword_canvas.set_font_size('48')

    def _shared_cb(self, activity):
        logger.debug('My Write activity was shared')
        self.initiating = True
        self._setup()
        
        self._shared_activity.connect('buddy-joined', self._buddy_joined_cb)
        self._shared_activity.connect('buddy-left', self._buddy_left_cb)

        logger.debug('This is my activity: offering a tube...')
        id = self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].OfferDBusTube(
            "com.abisource.abiword.abicollab", {})
        logger.debug('Tube address: %s', self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].GetDBusTubeAddress(id))


    def _setup(self):
        logger.debug("_setup()")

        if self._shared_activity is None:
            logger.error('Failed to share or join activity')
            return

        bus_name, conn_path, channel_paths = self._shared_activity.get_channels()

        # Work out what our room is called and whether we have Tubes already
        room = None
        tubes_chan = None
        text_chan = None
        for channel_path in channel_paths:
            channel = telepathy.client.Channel(bus_name, channel_path)
            htype, handle = channel.GetHandle()
            if htype == telepathy.HANDLE_TYPE_ROOM:
                logger.debug('Found our room: it has handle#%d "%s"',
                    handle, self.conn.InspectHandles(htype, [handle])[0])
                room = handle
                ctype = channel.GetChannelType()
                if ctype == telepathy.CHANNEL_TYPE_TUBES:
                    logger.debug('Found our Tubes channel at %s', channel_path)
                    tubes_chan = channel
                elif ctype == telepathy.CHANNEL_TYPE_TEXT:
                    logger.debug('Found our Text channel at %s', channel_path)
                    text_chan = channel

        if room is None:
            logger.error("Presence service didn't create a room")
            return
        if text_chan is None:
            logger.error("Presence service didn't create a text channel")
            return

        # Make sure we have a Tubes channel - PS doesn't yet provide one
        if tubes_chan is None:
            logger.debug("Didn't find our Tubes negotation channel, requesting one...")
            tubes_chan = self.conn.request_channel(telepathy.CHANNEL_TYPE_TUBES,
                telepathy.HANDLE_TYPE_ROOM, room, True)
            logger.debug("Got our tubes negotiation channel")

        self.tubes_chan = tubes_chan
        self.text_chan = text_chan

        tubes_chan[telepathy.CHANNEL_TYPE_TUBES].connect_to_signal('NewTube',
            self._new_tube_cb)

    def _list_tubes_reply_cb(self, tubes):
        for tube_info in tubes:
            self._new_tube_cb(*tube_info)

    def _list_tubes_error_cb(self, e):
        logger.error('ListTubes() failed: %s', e)

    def _joined_cb(self, activity):
        logger.debug("_joined_cb()")
        if not self._shared_activity:
            return

        self.joined = True
        logger.debug('Joined an existing Write session')
        self._setup()

        logger.debug('This is not my activity: waiting for a tube...')
        self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].ListTubes(
            reply_handler=self._list_tubes_reply_cb,
            error_handler=self._list_tubes_error_cb)

    def _new_tube_cb(self, id, initiator, type, service, params, state):
        logger.debug('New tube: ID=%d initiator=%d type=%d service=%s '
                     'params=%r state=%d', id, initiator, type, service,
                     params, state)

        if (type == telepathy.TUBE_TYPE_DBUS and
            service == "com.abisource.abiword.abicollab"):
            if state == telepathy.TUBE_STATE_LOCAL_PENDING:
                self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].AcceptDBusTube(id)

            initiator_path = None;
            contacts = self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].GetDBusNames(id)
            #print 'dbus contact mapping',self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].GetDBusNames(id)
            for i, struct in enumerate(contacts):
                #print 'mapping i',i
                handle, path = struct
                if handle == initiator:
                    logger.debug('found initiator dbus path: %s', path)
                    initiator_path = path
                    break;

            if initiator_path is None:
                logger.error('Unable to get the dbus path of the tube initiator')
            else:
                # pass this tube to abicollab
                address = self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].GetDBusTubeAddress(id)
                if self.joined:
                    logger.debug('Passing tube address to abicollab (join): %s', address)
                    self.abiword_canvas.invoke_cmd('com.abisource.abiword.abicollab.olpc.joinTube', address, 0, 0)
                    if initiator_path is not None:
                        logger.debug('Adding the initiator to the session: %s', initiator_path)
                        self.abiword_canvas.invoke_cmd('com.abisource.abiword.abicollab.olpc.buddyJoined', initiator_path, 0, 0)
                else:
                    logger.debug('Passing tube address to abicollab (offer): %s', address)
                    self.abiword_canvas.invoke_cmd('com.abisource.abiword.abicollab.olpc.offerTube', address, 0, 0)

            self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].connect_to_signal('DBusNamesChanged',
                self._on_dbus_names_changed)

            # HACK, as DBusNamesChanged doesn't fire on buddies leaving
            self.tubes_chan[telepathy.CHANNEL_INTERFACE_GROUP].connect_to_signal('MembersChanged',
                self._on_members_changed)

    def _on_dbus_names_changed(self, tube_id, added, removed):
        logger.debug('_on_dbus_names_changed')
#        if tube_id == self.tube_id:
        for handle, bus_name in added:
            logger.debug('added handle: %s, with dbus_name: %s', handle, bus_name)
            self.abiword_canvas.invoke_cmd('com.abisource.abiword.abicollab.olpc.buddyJoined', bus_name, 0, 0)
            self.participants[handle] = bus_name

#            if handle == self.self_handle:
                # I've just joined - set my unique name
#                print 'i\'ve just joined'
#                self.set_unique_name(bus_name)
#            self.participants[handle] = bus_name
#            self.bus_name_to_handle[bus_name] = handle

# HACK: doesn't work yet, bad morgs!
#        for handle in removed:
#            logger.debug('removed handle: %s, with dbus name: %s', handle, bus_name)
#            bus_name = self.participants.pop(handle, None)

    def _on_members_changed(self, message, added, removed, local_pending, remote_pending, actor, reason):
        logger.debug("_on_members_changed")
        for handle in removed:
            bus_name = self.participants.pop(handle, None)
            if bus_name is None:
                # FIXME: that shouldn't happen so probably hide another bug.
                # Should be investigated
                continue

            logger.debug('removed handle: %d, with dbus name: %s', handle,
                         bus_name)
            self.abiword_canvas.invoke_cmd('com.abisource.abiword.abicollab.olpc.buddyLeft', bus_name, 0, 0)

    def _buddy_joined_cb (self, activity, buddy):
        logger.debug('buddy joined with object path: %s', buddy.object_path())
#        self.abiword_canvas.invoke_cmd('com.abisource.abiword.abicollab.olpc.buddyJoined', buddy.object_path(), 0, 0)

    def _buddy_left_cb (self,  activity, buddy):
        logger.debug('buddy left with object path: %s', buddy.object_path())
        #self.abiword_canvas.invoke_cmd('com.abisource.abiword.abicollab.olpc.buddyLeft', self.participants[buddy.object_path()], 0, 0)

    def read_file(self, file_path):
        logging.debug('AbiWordActivity.read_file: %s, mimetype: %s', file_path, self.metadata['mime_type'])
        if 'source' in self.metadata and self.metadata['source'] == '1':
            logger.debug('Opening file in view source mode')
            self.abiword_canvas.load_file('file://' + file_path, 'text/plain') 
        else:
            self.abiword_canvas.load_file('file://' + file_path, '') # we pass no mime/file type, let libabiword autodetect it, so we can handle multiple file formats

    def write_file(self, file_path):
        logging.debug('AbiWordActivity.write_file')

        # check if we have a default mimetype; if not, fall back to OpenDocument
        if 'mime_type' not in self.metadata or self.metadata['mime_type'] == '':
            self.metadata['mime_type'] = 'application/vnd.oasis.opendocument.text'

        # if we were viewing the source of a file, 
        # then always save as plain text
        actual_mimetype = self.metadata['mime_type'];
        if 'source' in self.metadata and self.metadata['source'] == '1':
            logger.debug('Writing file as type source (text/plain)')
            actual_mimetype = 'text/plain'

        self.metadata['fulltext'] = self.abiword_canvas.get_content(extension_or_mimetype=".txt")[:3000]
        self.abiword_canvas.save('file://' + file_path, actual_mimetype, '');

    def _selection_cb(self, abi, b):
        self._edit_toolbar.copy.set_sensitive(True)

    def _selection_cleared_cb(self, abi, b):
        self._edit_toolbar.copy.set_sensitive(False)

    ########################################################################

    def texto_escribir(self, widget, txt):
	hbox = widget.get_children()[0]
	label = hbox.get_children()[0]
	el_txt = label.get_text()
	try:
	        self.abiword_canvas.insert_data(el_txt)
	except:
		print "ERROR, al escribir texto"
	self.enfocar(self.abiword_canvas)

    def texto_escribir_texto(self, txt):
	try:
	        self.abiword_canvas.insert_data(txt)
	except:
		print "ERROR, al escribir texto: " + txt
	self.enfocar(self.abiword_canvas)

    def borrar(self, *arg):
        self.abiword_canvas.delete_left()
	self.enfocar(self.abiword_canvas)

    def enter(self, *arg):
        self.abiword_canvas.insert_data("\n")
	self.enfocar(self.abiword_canvas)

    def espacio(self, *arg):
        self.abiword_canvas.insert_data(" ")
	self.enfocar(self.abiword_canvas)

    def tab(self, *arg):
        self.abiword_canvas.insert_data("	")
	self.enfocar(self.abiword_canvas)

    def espacio(self, *arg):
        self.abiword_canvas.insert_data(" ")
	self.enfocar(self.abiword_canvas)

    def mostrar_teclado(self):
	child = gtk.VBox(False, 2)

	self.btn_do = self.new_button_escribir("º")
	self.losBotones.append(self.btn_do)
	self.fila_1.append(self.btn_do)

	self.btn_1 = self.new_button_escribir("1")
	self.losBotones.append(self.btn_1)
	self.fila_1.append(self.btn_1)

	self.btn_2 = self.new_button_escribir("2")
	self.losBotones.append(self.btn_2)
	self.fila_1.append(self.btn_2)

	self.btn_3 = self.new_button_escribir("3")
	self.losBotones.append(self.btn_3)
	self.fila_1.append(self.btn_3)

	self.btn_4 = self.new_button_escribir("4")
	self.losBotones.append(self.btn_4)
	self.fila_1.append(self.btn_4)

	self.btn_5 = self.new_button_escribir("5")
	self.losBotones.append(self.btn_5)
	self.fila_1.append(self.btn_5)

	self.btn_6 = self.new_button_escribir("6")
	self.losBotones.append(self.btn_6)
	self.fila_1.append(self.btn_6)

	self.btn_7 = self.new_button_escribir("7")
	self.losBotones.append(self.btn_7)
	self.fila_1.append(self.btn_7)
	
	self.btn_8 = self.new_button_escribir("8")
	self.losBotones.append(self.btn_8)
	self.fila_1.append(self.btn_8)

	self.btn_9 = self.new_button_escribir("9")
	self.losBotones.append(self.btn_9)
	self.fila_1.append(self.btn_9)

	self.btn_0 = self.new_button_escribir("0")
	self.losBotones.append(self.btn_0)
	self.fila_1.append(self.btn_0)

	self.btn_finPreg = self.new_button_escribir("?")
	self.losBotones.append(self.btn_finPreg)
	self.fila_1.append(self.btn_finPreg)

	self.btn_inicioPreg = self.new_button_escribir("¿")
	self.losBotones.append(self.btn_inicioPreg)
	self.fila_1.append(self.btn_inicioPreg)

	self.btn_TAB = self.new_button_tab()
	self.losBotones.append(self.btn_TAB)
	self.fila_2.append(self.btn_TAB)

	self.btn_Q = self.new_button_escribir("Q")
	self.losBotones.append(self.btn_Q)
	self.fila_2.append(self.btn_Q)

	self.btn_W = self.new_button_escribir("W")
	self.losBotones.append(self.btn_W)
	self.fila_2.append(self.btn_W)

	self.btn_E = self.new_button_escribir("E")
	self.losBotones.append(self.btn_E)
	self.fila_2.append(self.btn_E)

	self.btn_R = self.new_button_escribir("R")
	self.losBotones.append(self.btn_R)
	self.fila_2.append(self.btn_R)

	self.btn_T = self.new_button_escribir("T")
	self.losBotones.append(self.btn_T)
	self.fila_2.append(self.btn_T)

	self.btn_Y = self.new_button_escribir("Y")
	self.losBotones.append(self.btn_Y)
	self.fila_2.append(self.btn_Y)

	self.btn_U = self.new_button_escribir("U")	
	self.losBotones.append(self.btn_U)
	self.fila_2.append(self.btn_U)

	self.btn_I = self.new_button_escribir("I")
	self.losBotones.append(self.btn_I)
	self.fila_2.append(self.btn_I)

	self.btn_O = self.new_button_escribir("O")
	self.losBotones.append(self.btn_O)
	self.fila_2.append(self.btn_O)

	self.btn_P = self.new_button_escribir("P")
	self.losBotones.append(self.btn_P)
	self.fila_2.append(self.btn_P)

	self.btn_tilde_derecho = self.new_button_escribir("'")
	self.losBotones.append(self.btn_tilde_derecho)
	self.fila_2.append(self.btn_tilde_derecho)

	self.btn_cierra_llave = self.new_button_escribir("]")
	self.losBotones.append(self.btn_cierra_llave )
	self.fila_2.append(self.btn_cierra_llave)

	self.btn_A = self.new_button_escribir("A")
	self.losBotones.append(self.btn_A)
	self.fila_3.append(self.btn_A)

	self.btn_S = self.new_button_escribir("S")
	self.losBotones.append(self.btn_S)
	self.fila_3.append(self.btn_S)

	self.btn_D = self.new_button_escribir("D")
	self.losBotones.append(self.btn_D)
	self.fila_3.append(self.btn_D)

	self.btn_F = self.new_button_escribir("F")
	self.losBotones.append(self.btn_F)
	self.fila_3.append(self.btn_F)

	self.btn_G = self.new_button_escribir("G")
	self.losBotones.append(self.btn_G)
	self.fila_3.append(self.btn_G)

	self.btn_H = self.new_button_escribir("H")
	self.losBotones.append(self.btn_H)
	self.fila_3.append(self.btn_H)

	self.btn_J = self.new_button_escribir("J")
	self.losBotones.append(self.btn_J)
	self.fila_3.append(self.btn_J)

	self.btn_K = self.new_button_escribir("K")
	self.losBotones.append(self.btn_K)
	self.fila_3.append(self.btn_K)

	self.btn_L = self.new_button_escribir("L")
	self.losBotones.append(self.btn_L)
	self.fila_3.append(self.btn_L)

	self.btn_enie = self.new_button_escribir("Ñ")
	self.losBotones.append(self.btn_enie)
	self.fila_3.append(self.btn_enie)

	self.btn_mas = self.new_button_escribir("+")
	self.losBotones.append(self.btn_mas)
	self.fila_3.append(self.btn_mas)

	self.btn_abre_llave = self.new_button_escribir("[")
	self.losBotones.append(self.btn_abre_llave)
	self.fila_3.append(self.btn_abre_llave)

	self.btn_menor = self.new_button_escribir("<")
	self.losBotones.append(self.btn_menor)
	self.fila_4.append(self.btn_menor)

	self.btn_Z = self.new_button_escribir("Z")
	self.losBotones.append(self.btn_Z)
	self.fila_4.append(self.btn_Z)

	self.btn_X = self.new_button_escribir("X")
	self.losBotones.append(self.btn_X)
	self.fila_4.append(self.btn_X)

	self.btn_C = self.new_button_escribir("C")
	self.losBotones.append(self.btn_C)
	self.fila_4.append(self.btn_C)

	self.btn_V = self.new_button_escribir("V")
	self.losBotones.append(self.btn_V)
	self.fila_4.append(self.btn_V)

	self.btn_B = self.new_button_escribir("B")
	self.losBotones.append(self.btn_B)
	self.fila_4.append(self.btn_B)

	self.btn_N = self.new_button_escribir("N")
	self.losBotones.append(self.btn_N)
	self.fila_4.append(self.btn_N)

	self.btn_M = self.new_button_escribir("M")
	self.losBotones.append(self.btn_M)
	self.fila_4.append(self.btn_M)

	self.btn_coma = self.new_button_escribir(",")
	self.losBotones.append(self.btn_coma)
	self.fila_4.append(self.btn_coma)

	self.btn_punto = self.new_button_escribir(".")
	self.losBotones.append(self.btn_punto)
	self.fila_4.append(self.btn_punto)

	self.btn_guion = self.new_button_escribir("-")
	self.losBotones.append(self.btn_guion)
	self.fila_4.append(self.btn_guion)

	self.btn_equivale = self.new_button_escribir("~")
	self.losBotones.append(self.btn_equivale)
	self.fila_4.append(self.btn_equivale)

	self.btn_A_tilde = self.new_button_escribir("Á")
	self.losBotones.append(self.btn_A_tilde)
	self.fila_5.append(self.btn_A_tilde)

	self.btn_E_tilde = self.new_button_escribir("É")
	self.losBotones.append(self.btn_E_tilde)
	self.fila_5.append(self.btn_E_tilde)

	self.btn_I_tilde = self.new_button_escribir("Í")
	self.losBotones.append(self.btn_I_tilde)
	self.fila_5.append(self.btn_I_tilde)

	self.btn_O_tilde = self.new_button_escribir("Ó")
	self.losBotones.append(self.btn_O_tilde)
	self.fila_5.append(self.btn_O_tilde)

	self.btn_U_tilde = self.new_button_escribir("Ú")
	self.losBotones.append(self.btn_U_tilde)
	self.fila_5.append(self.btn_U_tilde)

	self.btn_U_puntos = self.new_button_escribir("Ü")
	self.losBotones.append(self.btn_U_puntos)
	self.fila_5.append(self.btn_U_puntos)

	self.btn_pite = self.new_button_escribir("|")
	self.losBotones.append(self.btn_pite)
	self.fila_5.append(self.btn_pite)

	self.btn_arroba = self.new_button_escribir("@")
	self.losBotones.append(self.btn_arroba)
	self.fila_5.append(self.btn_arroba)

	self.btn_numeral = self.new_button_escribir("#")
	self.losBotones.append(self.btn_numeral)
	self.fila_5.append(self.btn_numeral)

	self.btn_techito = self.new_button_escribir("^")
	self.losBotones.append(self.btn_techito)
	self.fila_5.append(self.btn_techito)

	self.btn_contra_barra = self.new_button_escribir("\\")
	self.losBotones.append(self.btn_contra_barra)
	self.fila_5.append(self.btn_contra_barra)

	#controles especiales

	self.chk_activarBarrido_botones = gtk.CheckButton("_BOTONES")
	self.chk_activarBarrido_botones_menu = gtk.CheckButton("MENÚ")	
	self.fila_5.append(self.chk_activarBarrido_botones_menu)	

	self.chk_activarBarrido_botones.set_no_show_all(True)
	self.chk_activarBarrido_botones_menu.set_no_show_all(True)

	self.chk_activarBarrido_botones.show()

	self.losBotones.append(self.chk_activarBarrido_botones_menu)
	self.cbo_time_btn = self.combo_tiempos_botones()

	self.chk_activarBarrido_botones.connect("toggled", self.set_botonesXbarridoXfila)
	self.chk_activarBarrido_botones_menu.connect("toggled", self.set_botonesXbarrido_menu)

	#controles especiales

	# defino botones
	self.btn_SPACE = self.new_button_espacio()
	self.losBotones.append(self.btn_SPACE)
	self.fila_6.append(self.btn_SPACE)

	self.btn_BACK_SPACE = self.new_button_borrar()
	self.losBotones.append(self.btn_BACK_SPACE)
	self.fila_1.append(self.btn_BACK_SPACE)

	self.btn_ENTER = self.new_button_enter()
	self.losBotones.append(self.btn_ENTER)
	self.fila_2.append(self.btn_ENTER)
	self.fila_3.append(self.btn_ENTER)

	self.btn_CAPS_LOCK = self.new_button_mayuscula()
	self.losBotones.append(self.btn_CAPS_LOCK)
	self.fila_4.append(self.btn_CAPS_LOCK)

	self.set_connect_focus_btn()

	#dibujo tabla
	self.table = gtk.Table(7, 15, False) #5 filas, 4 columnas

	# márgenes: set_row_spacing(fil, tamaño en px) 
	self.table.set_row_spacing(0, 15)
	self.table.set_row_spacing(3, 15)
	self.table.set_col_spacing(12, 15)	
	self.table.set_row_spacing(4, 10)

	# attach(colIZQ, colDER, filSUP, filINF)
	self.table.attach(self.btn_do, 0, 1, 0, 1)
	self.table.attach(self.btn_1, 1, 2, 0, 1)
	self.table.attach(self.btn_2, 2, 3, 0, 1)
	self.table.attach(self.btn_3, 3, 4, 0, 1)
	self.table.attach(self.btn_4, 4, 5, 0, 1)
	self.table.attach(self.btn_5, 5, 6, 0, 1)
	self.table.attach(self.btn_6, 6, 7, 0, 1)
	self.table.attach(self.btn_7, 7, 8, 0, 1)
	self.table.attach(self.btn_8, 8, 9, 0, 1)
	self.table.attach(self.btn_9, 9, 10, 0, 1)
	self.table.attach(self.btn_0, 10, 11, 0, 1)
	self.table.attach(self.btn_finPreg, 11 ,12, 0, 1)
	self.table.attach(self.btn_inicioPreg, 12, 13, 0, 1)
	self.table.attach(self.btn_TAB, 0, 1, 1, 2)
	self.table.attach(self.btn_Q, 1, 2, 1, 2)
	self.table.attach(self.btn_W, 2, 3, 1, 2)
	self.table.attach(self.btn_E, 3, 4, 1, 2)
	self.table.attach(self.btn_R, 4, 5, 1, 2)
	self.table.attach(self.btn_T, 5, 6, 1, 2)
	self.table.attach(self.btn_Y, 6, 7, 1, 2)
	self.table.attach(self.btn_U, 7, 8, 1, 2)
	self.table.attach(self.btn_I, 8, 9, 1, 2)
	self.table.attach(self.btn_O, 9, 10, 1, 2)
	self.table.attach(self.btn_P, 10, 11, 1, 2)
	self.table.attach(self.btn_tilde_derecho, 11, 12, 1, 2)
	self.table.attach(self.btn_cierra_llave, 12, 13, 1, 2)
	self.table.attach(self.btn_A, 1, 2, 2, 3)
	self.table.attach(self.btn_S, 2, 3, 2, 3)
	self.table.attach(self.btn_D, 3, 4, 2, 3)
	self.table.attach(self.btn_F, 4, 5, 2, 3)
	self.table.attach(self.btn_G, 5, 6, 2, 3)
	self.table.attach(self.btn_H, 6, 7, 2, 3)
	self.table.attach(self.btn_J, 7, 8, 2, 3)
	self.table.attach(self.btn_K, 8, 9, 2, 3)
	self.table.attach(self.btn_L, 9, 10, 2, 3)
	self.table.attach(self.btn_enie, 10, 11, 2, 3)
	self.table.attach(self.btn_mas, 11, 12, 2, 3)
	self.table.attach(self.btn_abre_llave, 12, 13, 2, 3)
	self.table.attach(self.btn_menor, 0, 1, 3, 4)
	self.table.attach(self.btn_Z, 1, 2, 3, 4)
	self.table.attach(self.btn_X, 2, 3, 3, 4)
	self.table.attach(self.btn_C, 3, 4, 3, 4)
	self.table.attach(self.btn_V, 4, 5, 3, 4)
	self.table.attach(self.btn_B, 5, 6, 3, 4)
	self.table.attach(self.btn_N, 6, 7, 3, 4)
	self.table.attach(self.btn_M, 7, 8, 3, 4)
	self.table.attach(self.btn_coma, 8, 9, 3, 4)
	self.table.attach(self.btn_punto, 9, 10, 3, 4)
	self.table.attach(self.btn_guion, 10, 11, 3, 4)
	self.table.attach(self.btn_equivale, 11, 12, 3, 4)

	self.table.attach(self.btn_BACK_SPACE, 13, 15, 0, 1)
	self.table.attach(self.btn_ENTER, 13, 15, 1, 3)
	self.table.attach(self.btn_CAPS_LOCK, 13, 15, 3, 4)
	self.table.attach(self.chk_activarBarrido_botones_menu, 13, 14, 4, 5)	
	self.table.attach(self.chk_activarBarrido_botones, 13, 14, 5, 6)
	self.table.attach(self.cbo_time_btn, 14, 15, 5, 6)
	self.table.attach(self.btn_SPACE, 1, 13, 5, 6)

	self.table.attach(self.btn_A_tilde, 1, 2, 4, 5)
	self.table.attach(self.btn_E_tilde, 2, 3, 4, 5)
	self.table.attach(self.btn_I_tilde, 3, 4, 4, 5)
	self.table.attach(self.btn_O_tilde, 4, 5, 4, 5)
	self.table.attach(self.btn_U_tilde, 5, 6, 4, 5)
	self.table.attach(self.btn_U_puntos, 7, 8, 4, 5)
	
	self.table.attach(self.btn_pite, 8, 9, 4, 5)
	self.table.attach(self.btn_arroba, 9, 10, 4, 5)
	self.table.attach(self.btn_numeral, 10, 11, 4, 5)
	self.table.attach(self.btn_techito, 11, 12, 4, 5)
	self.table.attach(self.btn_contra_barra, 12, 13, 4, 5)

	child.pack_end(self.table, True, True, 0)      

	return child

    def set_mayuscula(self, *arg):
	if (self.MAYUSCULA):
		self.btn_do.get_children()[0].get_children()[0].set_text("ª")
		self.btn_1.get_children()[0].get_children()[0].set_text("!")
		self.btn_2.get_children()[0].get_children()[0].set_text("\"")
		self.btn_3.get_children()[0].get_children()[0].set_text("`")
		self.btn_4.get_children()[0].get_children()[0].set_text("$")
		self.btn_5.get_children()[0].get_children()[0].set_text("%")
		self.btn_6.get_children()[0].get_children()[0].set_text("&")
		self.btn_7.get_children()[0].get_children()[0].set_text("/")
		self.btn_8.get_children()[0].get_children()[0].set_text("(")
		self.btn_9.get_children()[0].get_children()[0].set_text(")")
		self.btn_0.get_children()[0].get_children()[0].set_text("=")
		self.btn_finPreg.get_children()[0].get_children()[0].set_text("?")
		self.btn_inicioPreg.get_children()[0].get_children()[0].set_text("¿")
		self.btn_Q.get_children()[0].get_children()[0].set_text("q")
		self.btn_W.get_children()[0].get_children()[0].set_text("w")
		self.btn_E.get_children()[0].get_children()[0].set_text("e")
		self.btn_R.get_children()[0].get_children()[0].set_text("r")
		self.btn_T.get_children()[0].get_children()[0].set_text("t")
		self.btn_Y.get_children()[0].get_children()[0].set_text("y")
		self.btn_U.get_children()[0].get_children()[0].set_text("u")
		self.btn_I.get_children()[0].get_children()[0].set_text("i")
		self.btn_O.get_children()[0].get_children()[0].set_text("o")
		self.btn_P.get_children()[0].get_children()[0].set_text("p")
		self.btn_A.get_children()[0].get_children()[0].set_text("a")
		self.btn_S.get_children()[0].get_children()[0].set_text("s")
		self.btn_D.get_children()[0].get_children()[0].set_text("d")
		self.btn_F.get_children()[0].get_children()[0].set_text("f")
		self.btn_G.get_children()[0].get_children()[0].set_text("g")
		self.btn_H.get_children()[0].get_children()[0].set_text("h")
		self.btn_J.get_children()[0].get_children()[0].set_text("j")
		self.btn_K.get_children()[0].get_children()[0].set_text("k")
		self.btn_L.get_children()[0].get_children()[0].set_text("l")
		self.btn_enie.get_children()[0].get_children()[0].set_text("ñ")
		self.btn_menor.get_children()[0].get_children()[0].set_text(">")
		self.btn_Z.get_children()[0].get_children()[0].set_text("z")
		self.btn_X.get_children()[0].get_children()[0].set_text("x")
		self.btn_C.get_children()[0].get_children()[0].set_text("c")
		self.btn_V.get_children()[0].get_children()[0].set_text("v")
		self.btn_B.get_children()[0].get_children()[0].set_text("b")
		self.btn_N.get_children()[0].get_children()[0].set_text("n")
		self.btn_M.get_children()[0].get_children()[0].set_text("m")
		self.btn_coma.get_children()[0].get_children()[0].set_text(";")
		self.btn_punto.get_children()[0].get_children()[0].set_text(":")
		self.btn_guion.get_children()[0].get_children()[0].set_text("_")
		self.btn_A_tilde.get_children()[0].get_children()[0].set_text("á")
		self.btn_E_tilde.get_children()[0].get_children()[0].set_text("é")
		self.btn_I_tilde.get_children()[0].get_children()[0].set_text("í")
		self.btn_O_tilde.get_children()[0].get_children()[0].set_text("ó")
		self.btn_U_tilde.get_children()[0].get_children()[0].set_text("ú")
		self.btn_U_puntos.get_children()[0].get_children()[0].set_text("ü")
		self.btn_mas.get_children()[0].get_children()[0].set_text("*")
		self.btn_tilde_derecho.get_children()[0].get_children()[0].set_text("\"")
		self.btn_abre_llave.get_children()[0].get_children()[0].set_text("{")
		self.btn_cierra_llave.get_children()[0].get_children()[0].set_text("}")

		self.MAYUSCULA = False
		self.btn_CAPS_LOCK.get_children()[0].get_children()[0].set_text("MAYÚSCULAS")
	else:
		self.btn_do.get_children()[0].get_children()[0].set_text("º")
		self.btn_1.get_children()[0].get_children()[0].set_text("1")
		self.btn_2.get_children()[0].get_children()[0].set_text("2")
		self.btn_3.get_children()[0].get_children()[0].set_text("3")
		self.btn_4.get_children()[0].get_children()[0].set_text("4")
		self.btn_5.get_children()[0].get_children()[0].set_text("5")
		self.btn_6.get_children()[0].get_children()[0].set_text("6")
		self.btn_7.get_children()[0].get_children()[0].set_text("7")
		self.btn_8.get_children()[0].get_children()[0].set_text("8")
		self.btn_9.get_children()[0].get_children()[0].set_text("9")
		self.btn_0.get_children()[0].get_children()[0].set_text("0")
		self.btn_finPreg.get_children()[0].get_children()[0].set_text("'")
		self.btn_inicioPreg.get_children()[0].get_children()[0].set_text("¡")
		self.btn_Q.get_children()[0].get_children()[0].set_text("Q")
		self.btn_W.get_children()[0].get_children()[0].set_text("W")
		self.btn_E.get_children()[0].get_children()[0].set_text("E")
		self.btn_R.get_children()[0].get_children()[0].set_text("R")
		self.btn_T.get_children()[0].get_children()[0].set_text("T")
		self.btn_Y.get_children()[0].get_children()[0].set_text("Y")
		self.btn_U.get_children()[0].get_children()[0].set_text("U")
		self.btn_I.get_children()[0].get_children()[0].set_text("I")
		self.btn_O.get_children()[0].get_children()[0].set_text("O")
		self.btn_P.get_children()[0].get_children()[0].set_text("P")
		self.btn_A.get_children()[0].get_children()[0].set_text("A")
		self.btn_S.get_children()[0].get_children()[0].set_text("S")
		self.btn_D.get_children()[0].get_children()[0].set_text("D")
		self.btn_F.get_children()[0].get_children()[0].set_text("F")
		self.btn_G.get_children()[0].get_children()[0].set_text("G")
		self.btn_H.get_children()[0].get_children()[0].set_text("H")
		self.btn_J.get_children()[0].get_children()[0].set_text("J")
		self.btn_K.get_children()[0].get_children()[0].set_text("K")
		self.btn_L.get_children()[0].get_children()[0].set_text("L")
		self.btn_enie.get_children()[0].get_children()[0].set_text("Ñ")
		self.btn_menor.get_children()[0].get_children()[0].set_text("<")
		self.btn_Z.get_children()[0].get_children()[0].set_text("Z")
		self.btn_X.get_children()[0].get_children()[0].set_text("X")
		self.btn_C.get_children()[0].get_children()[0].set_text("C")
		self.btn_V.get_children()[0].get_children()[0].set_text("V")
		self.btn_B.get_children()[0].get_children()[0].set_text("B")
		self.btn_N.get_children()[0].get_children()[0].set_text("N")
		self.btn_M.get_children()[0].get_children()[0].set_text("M")
		self.btn_coma.get_children()[0].get_children()[0].set_text(",")
		self.btn_punto.get_children()[0].get_children()[0].set_text(".")
		self.btn_guion.get_children()[0].get_children()[0].set_text("-")
		self.btn_A_tilde.get_children()[0].get_children()[0].set_text("Á")
		self.btn_E_tilde.get_children()[0].get_children()[0].set_text("É")
		self.btn_I_tilde.get_children()[0].get_children()[0].set_text("Í")
		self.btn_O_tilde.get_children()[0].get_children()[0].set_text("Ó")
		self.btn_U_tilde.get_children()[0].get_children()[0].set_text("Ú")
		self.btn_U_puntos.get_children()[0].get_children()[0].set_text("Ü")
		self.btn_mas.get_children()[0].get_children()[0].set_text("+")
		self.btn_tilde_derecho.get_children()[0].get_children()[0].set_text("'")
		self.btn_abre_llave.get_children()[0].get_children()[0].set_text("[")
		self.btn_abre_llave.get_children()[0].get_children()[0].set_text("]")

		self.MAYUSCULA = True
		self.btn_CAPS_LOCK.get_children()[0].get_children()[0].set_text("MINÚSCULAS")
	self.enfocar(self.abiword_canvas)


    def set_botonesXbarrido(self, widget):
	state = widget.get_active()
	if state:	
		self.chk_activarBarrido_botones_menu.show()
		#self.controles_menu_item_set_barrido(True)
		self.BOTONESxBARRIDO = True
		self.BOTONESxBARRIDO_MENU = False		
		self.botonesXbarrido()
	else:
		self.chk_activarBarrido_botones_menu.hide()
		#self.controles_menu_item_set_barrido(False)
		self.BOTONESxBARRIDO = False

    def botonesXbarrido(self):
	
	self.posicionar_puntero()
	HILO_A = threading.Thread(target = self.barrerFocus)
	HILO_A.start()
	HILO_A.quit = True
	HILO_A.join(1)

    def barrerFocus(self):
	while self.BOTONESxBARRIDO:	
		for btn in self.losBotones:
			seg=self.get_time_barrido_botones()		
			if not self.BOTONESxBARRIDO:
				break
			time.sleep(seg)
			if not self.BOTONESxBARRIDO:
				break
			btn.grab_focus()
			self.btn_actual = btn

    def mouse_boton(self, widget, event):
	self.bloquearHandler()
	if self.BOTONESxBARRIDO_MENU_ITEM:
		self.BOTONESxBARRIDO_MENU_ITEM = False
		self.controles_menu_item_set_barrido(True)
		self.chk_activarBarrido_botones_menu.emit("clicked") # le saca el barrido a los botones.		
		self.ejecutarAccion()
		#volver a barrer
		return
	else:
		self.controles_menu_item_set_barrido(False) # desconecta el barrido de los menu item

	if self.BOTONESxBARRIDO_MENU:
		self.BOTONESxBARRIDO_MENU = False
		self.BOTONESxBARRIDO_MENU_ITEM = True
		self.chk_activarBarrido_botones.emit("clicked") # le saca el barrido a los botones.
		self.botonesXbarrido_menu_item()
		return
	if self.BOTONESxBARRIDO:
		self.BOTONESxBARRIDO=False
		if type(self.btn_actual) == type(gtk.Button()): #si es un boton			
			self.escribir_boton()
			#voler a empezar...
			self.enfocar(self.abiword_canvas)
			self.BOTONESxBARRIDOxFILA = True
			self.botonesXbarridoXfila()
		if type(self.btn_actual) == type(gtk.CheckButton()):
			self.btn_actual.emit("clicked")
		return
	if self.BOTONESxBARRIDOxFILA:
		if self.fila_actual_nro==6: #es el boton space
			self.espacio()
			self.iluminarFila(self.fila_actual_nro, "white")
		else:
			self.BOTONESxBARRIDOxFILA = False;
			self.iluminarFila(self.fila_actual_nro, "white")
			self.BOTONESxBARRIDO = True;
			self.botonesXbarridoEnFila()


    def escribir_boton(self, *arg):
	hbox = self.btn_actual.get_children()[0]
	label = hbox.get_children()[0]
	txt = label.get_text()
	if txt == "ENTER":
		self.enter()
		return
	if txt == "TAB":
		self.tab()	
		return
	if txt == "BORRAR":
		self.borrar()
		return
	if txt == "ESPACIO":
		self.espacio()
		return
	if txt == "MAYÚSCULAS" or txt == "MINÚSCULAS":
		self.set_mayuscula()
		return
	self.texto_escribir_texto(txt)

    def posicionar_puntero(self):
	#while self.BOTONESxBARRIDO: #tiene el problema q si cierra la actividad el puntero se qeuda ahi tal vez con hilos funque...
		d = display.Display()
		s = d.screen()
		root = s.root
		root.warp_pointer(40,335)
		d.sync()

    def on_focus_out_btn(self, w, e):	
	#w.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse("#7f7f7f")) # color x defecto
	w.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse("white"))

    def on_focus_in_btn(self, w, e):
	w.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse("Yellow"))


    def set_connect_focus_btn(self):
	for btn in self.losBotones:
		try:
			btn.connect('focus-in-event', self.on_focus_in_btn)
			btn.connect('focus-out-event', self.on_focus_out_btn)
		except:
			pass

    def new_button_escribir(self, plabel):
	btn = gtk.Button()
	hbox = gtk.HBox(False, 0)
	btn.add(hbox)
	label = gtk.Label(plabel)

	label.modify_font(pango.FontDescription("sans bold 13"))
	label.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse('black'))

	btn.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse("white"))

	label.set_use_underline(True)
	hbox.add(label)

	btn.connect("pressed", self.texto_escribir, plabel)
	btn.connect("activate", self.texto_escribir, plabel)
	return btn

    def new_button_enter(self):
	btn = gtk.Button()
	hbox = gtk.HBox(False, 0)
	btn.add(hbox)
	label = gtk.Label("ENTER")

	label.modify_font(pango.FontDescription("sans bold 13"))
	label.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse('black'))

	btn.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse("white"))

	label.set_use_underline(True)
	hbox.add(label)

	btn.connect("pressed", self.enter)
	btn.connect("activate", self.enter)
	return btn

    def new_button_espacio(self):
	btn = gtk.Button()
	hbox = gtk.HBox(False, 0)
	btn.add(hbox)
	label = gtk.Label("ESPACIO")

	label.modify_font(pango.FontDescription("sans bold 13"))
	label.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse('black'))

	btn.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse("white"))

	label.set_use_underline(True)
	hbox.add(label)

	btn.connect("pressed", self.espacio)
	btn.connect("activate", self.espacio)
	return btn

    def new_button_borrar(self):
	btn = gtk.Button()
	hbox = gtk.HBox(False, 0)
	btn.add(hbox)
	label = gtk.Label("BORRAR")

	label.modify_font(pango.FontDescription("sans bold 13"))
	label.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse('black'))

	btn.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse("white"))

	label.set_use_underline(True)
	hbox.add(label)

	btn.connect("pressed", self.borrar)
	btn.connect("activate", self.borrar)
	return btn

    def new_button_tab(self):
	btn = gtk.Button()
	hbox = gtk.HBox(False, 0)
	btn.add(hbox)
	label = gtk.Label("TAB")

	label.modify_font(pango.FontDescription("sans bold 13"))
	label.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse('black'))

	btn.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse("white"))

	label.set_use_underline(True)
	hbox.add(label)

	btn.connect("pressed", self.tab)
	btn.connect("activate", self.tab)
	return btn

    def new_button_mayuscula(self):
	btn = gtk.Button()
	hbox = gtk.HBox(False, 0)
	btn.add(hbox)
	label = gtk.Label("MINÚSCULAS")

	label.modify_font(pango.FontDescription("sans bold 13"))
	label.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse('black'))

	btn.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse("white"))

	label.set_use_underline(True)
	hbox.add(label)

	btn.connect("pressed", self.set_mayuscula)
	btn.connect("activate", self.set_mayuscula)
	return btn

    def get_time_barrido_botones(self):
    	return self.leer_config(get_bundle_path() + "/" + PATH_CONFIG_BARRIDO, 'botones', 'time')

    def set_time_barrido_botones(self, seg):
    	self.grabar_config(get_bundle_path() + "/" + PATH_CONFIG_BARRIDO, 'botones', 'time', seg)

    def grabar_config(self, path, encabezado, item, valor):
	parser = ConfigParser.ConfigParser()
	parser.read(path)
	if not parser.has_section(encabezado):
		arser.add_section(encabezado)
		arch = open(path, 'w')
		parser.write(arch)
		arch.close()
	parser.set(encabezado, item, valor)
	arch = open(path, 'w')
	parser.write(arch)
	arch.close()

    def leer_config(self, path, encabezado, item):
	parser = ConfigParser.ConfigParser()
	parser.read(path)
	if not parser.has_section(encabezado):
		return -1
	return float(parser.get(encabezado, item))

    def combo_tiempos_botones(self):
	cb = gtk.combo_box_new_text()
	cb.connect("changed", self.on_changed_cbo_time_btn)
	cb.append_text("RÁPIDO")
	cb.append_text("MEDIO")
	cb.append_text("LENTO")
	seg = 1
	try:
		seg = self.get_time_barrido_botones()									
	except:
		print "ERROR, al leer velocidad de barrido de botones"
		seg = velocidades['media']

	if seg==velocidades['rapida']:
		cb.set_active(0)
	if seg==velocidades['media']:
		cb.set_active(1)		
	if seg==velocidades['lenta']:
		cb.set_active(2)
			
	return cb

    def on_changed_cbo_time_btn(self, widget):
	s = widget.get_active()

	if s==0:
		seg = velocidades['rapida']
	if s==1:
		seg = velocidades['media']
	if s==2:
		seg = velocidades['lenta']
	
	self.set_time_barrido_botones(seg)

    def botonesXbarrido_menu(self):
	
	self.posicionar_puntero()
	HILO_B = threading.Thread(target = self.barrerFocus_menu)
	HILO_B.start()
	HILO_B.join(1)
	HILO_B.quit = True	

    def barrerFocus_menu(self):       
	cant = len(self.toolbox.get_children()[0].get_children())	
	i = -1
	while self.BOTONESxBARRIDO_MENU:
			if not self.BOTONESxBARRIDO_MENU:
				break
			if (cant == i + 1 ):
				i = 0
			else:
				i = i + 1
			if (not i==3) and (not i==4): #no barrer los menues imaen ni tabla
				time.sleep(self.get_time_barrido_botones())
			if not self.BOTONESxBARRIDO_MENU:
				break
			if (not i==3) and (not i==4): #no barrer los menues imagen ni tabla
				self.toolbox.get_children()[0].set_current_page(i)

    def set_botonesXbarrido_menu(self, widget):
	state = widget.get_active()
	if state:
		if (self.BOTONESxBARRIDOxFILA):
			self.BOTONESxBARRIDOxFILA = False
			self.iluminarFila(self.fila_actual_nro, "white")	
		self.BOTONESxBARRIDO = False
		self.BOTONESxBARRIDO_MENU = True		
		self.botonesXbarrido_menu()
	else:	
		#self.BOTONESxBARRIDOxFILA = True #ver
		self.BOTONESxBARRIDO_MENU = False

    def botonesXbarrido_menu_item(self):
	
	self.posicionar_puntero()
	HILO_B = threading.Thread(target = self.barrerFocus_menu_item)
	HILO_B.start()
	HILO_B.join(1)
	HILO_B.quit = True	

    def barrerFocus_menu_item(self):
	#agrega el boton para salir del barrido
	self.boton_salir_barrido_item(True)	
	cant_items = len(self.toolbox.get_children()[0].get_nth_page(self.toolbox.get_children()[0].get_current_page()).get_children()[0].get_children()[0].get_children()) # controles del toolbar actual
	while self.BOTONESxBARRIDO_MENU_ITEM:
		for i in range(0,cant_items):		
			if not self.BOTONESxBARRIDO_MENU_ITEM:
				self.boton_salir_barrido_item(False)
				break	

			c = self.toolbox.get_children()[0].get_nth_page(self.toolbox.get_children()[0].get_current_page()).get_children()[0].get_children()[0].get_children()[i]
			if (type(c)==type(ToggleToolButton()) or type(c)==type(ToolButton()) or type(c)==type(gtk.Button())):
				barrer = True
				if (type(c)==type(ToolButton())):
					if (self.esBotonTP(c)):
						barrer = False
				if (barrer):
					time.sleep(self.get_time_barrido_botones())
					if not self.BOTONESxBARRIDO_MENU_ITEM:
						self.boton_salir_barrido_item(False)
						break
					self.menu_item_actual = c.get_children()[0]	
					self.menu_item_actual.grab_focus()
			if (type(c)==type(ToolComboBox())):
				time.sleep(self.get_time_barrido_botones())
				if not self.BOTONESxBARRIDO_MENU_ITEM:
					self.boton_salir_barrido_item(False)
					break
				self.menu_item_actual = c.get_children()[0].get_children()[1]
				self.menu_item_actual.grab_focus()
	self.boton_salir_barrido_item(False)


    def ejecutarAccion(self):	
	try:
		if (type(self.menu_item_actual)==type(ComboBox())):
			self.menu_item_actual.emit("popup")	
		else:
			self.menu_item_actual.emit("clicked")
	except:
		pass
	#self.menu_item_actual.emit("activate")
	#ojo q algunos son label y cae si le hago emit eso...


    def controles_menu_item_set_barrido(self, conectar):	
	cant_items = len(self.toolbox.get_children()[0].get_nth_page(self.toolbox.get_children()[0].get_current_page()).get_children()[0].get_children()[0].get_children()) # controles del toolbar actual	
	for i in range(0,cant_items):
		try:
			c = self.toolbox.get_children()[0].get_nth_page(self.toolbox.get_children()[0].get_current_page()).get_children()[0].get_children()[0].get_children()[i]
			if (type(c)==type(ToggleToolButton()) or type(c)==type(ToolButton()) or type(c)==type(gtk.Button())):
				c = c.get_children()[0]
				if conectar:
					c.connect("clicked", self.barriendo)
				else:
					c.disconnect("clicked", self.barriendo)
			if (type(c)==type(ToolComboBox())):
				c = c.get_children()[0].get_children()[1]
				if conectar:
					c.connect("popup", self.cbo_barriendo)
				else:
					c.disconnect("popup", self.cbo_barriendo)
		except:	
			pass

    def barriendo (self, *arg):
	self.BOTONESxBARRIDO_MENU = False
	self.BOTONESxBARRIDO_MENU_ITEM = False
	self.chk_activarBarrido_botones.set_active(True)

    def cbo_barriendo(self, *arg):
	i = self.menu_item_actual.get_active()
	self.menu_item_actual.set_active(i+1)
	self.barriendo()

    def boton_salir_barrido_item(self, mostrar):
	if (mostrar):
		self.view_toolbar._btn_barrido_menu.show()
		self._edit_toolbar._btn_barrido_menu.show()
		self.text_toolbar._btn_barrido_menu.show()
		self.image_toolbar._btn_barrido_menu.show()
		self.table_toolbar._btn_barrido_menu.show()
		self.format_toolbar._btn_barrido_menu.show()
	else:
		self.view_toolbar._btn_barrido_menu.hide()
		self._edit_toolbar._btn_barrido_menu.hide()		
		self.text_toolbar._btn_barrido_menu.hide()
		self.image_toolbar._btn_barrido_menu.hide()
		self.table_toolbar._btn_barrido_menu.hide()
		self.format_toolbar._btn_barrido_menu.hide()

    def set_botonesXbarridoXfila(self, widget):
	state = widget.get_active()
	if state:	
		self.chk_activarBarrido_botones_menu.show()
		self.BOTONESxBARRIDOxFILA = True
		self.BOTONESxBARRIDO_MENU = False		
		self.botonesXbarridoXfila()
	else:
		self.chk_activarBarrido_botones_menu.hide()
		if (self.BOTONESxBARRIDOxFILA):
			self.BOTONESxBARRIDOxFILA = False
			self.iluminarFila(self.fila_actual_nro, "white")	
		self.BOTONESxBARRIDO = False

    def botonesXbarridoXfila(self):
	self.posicionar_puntero()
	HILO_A = threading.Thread(target = self.barrerFocusXfila)
	HILO_A.start()
	HILO_A.quit = True
	HILO_A.join(1)

    def barrerFocusXfila(self, *arg):
	while self.BOTONESxBARRIDOxFILA:
			seg = self.get_time_barrido_botones()
			if not self.BOTONESxBARRIDOxFILA:
				break
			self.fila_actual_nro = 1
			self.fila_actual = self.fila_1
			self.iluminarFila(6, "white")
			if not self.BOTONESxBARRIDOxFILA:
				break
			self.iluminarFila(1, "Yellow")
			if not self.BOTONESxBARRIDOxFILA:
				break
			time.sleep(seg+0.75)
			if not self.BOTONESxBARRIDOxFILA:
				break
			self.fila_actual_nro = 2
			self.fila_actual = self.fila_2
			self.iluminarFila(1, "white")
			if not self.BOTONESxBARRIDOxFILA:
				break
			self.iluminarFila(2, "Yellow")
			if not self.BOTONESxBARRIDOxFILA:
				break
			time.sleep(seg)
			if not self.BOTONESxBARRIDOxFILA:
				break
			self.fila_actual_nro = 3
			self.fila_actual = self.fila_3
			self.iluminarFila(2, "white")
			if not self.BOTONESxBARRIDOxFILA:
				break
			self.iluminarFila(3, "Yellow")
			if not self.BOTONESxBARRIDOxFILA:
				break
			time.sleep(seg)
			if not self.BOTONESxBARRIDOxFILA:
				break
			self.fila_actual_nro = 4
			self.fila_actual = self.fila_4
			self.iluminarFila(3, "white")
			if not self.BOTONESxBARRIDOxFILA:
				break
			self.iluminarFila(4, "Yellow")
			if not self.BOTONESxBARRIDOxFILA:
				break
			time.sleep(seg)
			if not self.BOTONESxBARRIDOxFILA:
				break
			self.fila_actual_nro = 5
			self.fila_actual = self.fila_5
			self.iluminarFila(4, "white")
			if not self.BOTONESxBARRIDOxFILA:
				break
			self.iluminarFila(5, "Yellow")
			if not self.BOTONESxBARRIDOxFILA:
				break
			time.sleep(seg)
			if not self.BOTONESxBARRIDOxFILA:
				break
			self.fila_actual_nro = 6
			self.fila_actual = self.fila_6
			self.iluminarFila(5, "white")
			if not self.BOTONESxBARRIDOxFILA:
				break
			self.iluminarFila(6, "Yellow")
			if not self.BOTONESxBARRIDOxFILA:
				break
			time.sleep(seg)
			if not self.BOTONESxBARRIDOxFILA:
				break
			

    def iluminarFila(self, fila, color):
	if fila == 1:
		for f in range(0,len(self.fila_1)):
			gobject.idle_add(self.pintarControl,self.fila_1[f], color)
	if fila == 2:
		for f in range(0,len(self.fila_2)):
			gobject.idle_add(self.pintarControl,self.fila_2[f], color)
	if fila == 3:
		for f in range(0,len(self.fila_3)):
			gobject.idle_add(self.pintarControl,self.fila_3[f], color)
	if fila == 4:
		for f in range(0,len(self.fila_4)):
			gobject.idle_add(self.pintarControl,self.fila_4[f], color)
	if fila == 5:
		for f in range(0,len(self.fila_5)):
			gobject.idle_add(self.pintarControl,self.fila_5[f], color)
	if fila == 6:
		for f in range(0,len(self.fila_6)):
			gobject.idle_add(self.pintarControl,self.fila_6[f], color)

    def pintarControl(self, w, color):
	w.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse(color))

    def botonesXbarridoEnFila(self):
	self.posicionar_puntero()
	HILO_A = threading.Thread(target = self.barrerFocusEnFila)
	HILO_A.start()
	HILO_A.quit = True

    def barrerFocusEnFila(self):
	i = 0
	while self.BOTONESxBARRIDO:
		if (i == 3):
			# si recorrio 3 veces empezar de nuevo...
			self.desenfocarXHilo()
			self.BOTONESxBARRIDO = False
			self.BOTONESxBARRIDOxFILA = True
			self.botonesXbarridoXfila()
			break		
		for btn in self.fila_actual:	
			seg=self.get_time_barrido_botones()		
			if not self.BOTONESxBARRIDO:
				break
			time.sleep(seg)
			if not self.BOTONESxBARRIDO:
				break
			self.btn_actual = btn
			gobject.idle_add(self.enfocar,btn)
		i = i + 1

    def bloquearHandler(self):
	HILO_A = threading.Thread(target = self.bloquearHandler_aux_obj)
	HILO_A.start()
	HILO_A.quit = True

    def bloquearHandler_aux_obj(self):
 	self.event_box.handler_block(self.ebc)
	seg=self.get_time_barrido_botones()
	if seg == velocidades['rapida']:
		time.sleep(seg-0.15)
	if seg == velocidades['media']:
		time.sleep(seg-0.30)
	if seg == velocidades['lenta']:
		time.sleep(seg-0.75)  
	self.event_box.handler_unblock(self.ebc)

    def enfocar(self, btn):
	btn.grab_focus()

    def desenfocarXHilo(self):
	HILO_A = threading.Thread(target = self.desenfocarXHiloXGobj)
	HILO_A.start()
	HILO_A.quit = True

    def desenfocarXHiloXGobj(self):
	gobject.idle_add(self.desenfocar)

    def desenfocar(self):
	self.abiword_canvas.grab_focus()

    def esBotonTP(self, btn):
	return (((btn.get_tooltip()=='Mostrar \nTeclado') or (btn.get_tooltip()=='Ocultar \nTeclado'))) 
