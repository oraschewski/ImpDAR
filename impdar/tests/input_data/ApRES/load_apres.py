#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 David Lilien <dlilien90@gmail.com>
#
# Distributed under terms of the GNU GPL3 license.

"""
Load ApRES data

uch of this code is either directly referencing or written from older scripts in SeisUnix:
https:ithub.com/JohnWStockwellJr/SeisUnix/wiki
Options are:
    Kirchhoff (diffraction summation)
    Stolt (frequency wavenumber, constant velocity)
    Gazdag (phase shift, either constant or depth-varying velocity)
    SeisUnix (reference su routines directly)

Author:
Benjamin Hills
bhills@uw.edu
University of Washington
Earth and Space Sciences

ar 12 2019

"""

import numpy as np
from ..RadarData import RadarData
from ..RadarFlags import RadarFlags


def load_apres(fn_apres,burst=1,fs=40000):
    """
    # Craig Stewart
    # 2013 April 24
    # 2013 September 30 - corrected error in vif scaling
    # 2014/5/20 time stamp moved here from fmcw_derive_parameters (so that this
    # is not overwritted later)
    # 2014/5/21 changed how radar chirp is defined (now using chirp gradient as
    # fundamental parameter)
    # 2014/5/22 fixed bug in chirptime
    # 2014/8/21 moved make odd length to external (called from fmcw_range)
    # 2014/10/22 KWN - edited to allow for new headers in RMB2 files
    """

    ## Load data and reshape array
    [path,~,ext] = fileparts(filename);
    if strcmp(ext,'.mat')
        load(filename); # note when you load a mat file you get whatever burst was stored in this - not the one you selected
        FileFormat = 'mat';
    else
        FileFormat = fmcw_file_format(filename);
        vdat = LoadBurstRMB5(filename, burst, SamplingFrequency);# Data from after Oct 2014 (RMB2b + VAB Iss C, SW Issue >= 101)
    end
    vdat.FileFormat = FileFormat;

    # Extract just good chirp data from voltage record and rearrange into
    # matrix with one chirp per row
    # note: you can't just use reshape as we are also cropping the 20K samples
    # of sync tone etc which occur after each 40K of chirp.
    AttSet = vdat.Attenuator_1 + 1i*vdat.Attenuator_2; # unique code for attenuator setting


    ## Add metadata to structure


    # Sampling parameters
    vdat.filename = filename;
    if ~ischar(FileFormat)
        vdat.SamplesPerChirp = vdat.Nsamples;
        vdat.fs = 4e4; # sampling frequency
        vdat.f0 = 2e8; # start frequency
        #vdat.fc = 3e8; # start frequency
        vdat.K = 2*pi*2e8; # chirp gradient in rad/s/s (200MHz/s)
        #vdat.f0 = vdat.f0 + (vdat.K/(4*pi))/vdat.fs; # start frequency
        vdat.processing = {};

        if FileFormat == 5
            H = fmcw_ParametersRMB2(vdat.filename);
        elseif FileFormat == 4
            H = fmcw_ParametersRMB1b(vdat.filename);
        end
        if FileFormat == 5 || FileFormat == 4
            vdat.K = H.K;
            vdat.f0 = H.startFreq;
            vdat.fs = H.fs;
            vdat.f1 = H.startFreq + H.chirpLength * H.K/2/pi;
            vdat.SamplesPerChirp = round(H.chirpLength * H.fs);
            vdat.T = H.chirpLength;
            vdat.B = H.chirpLength * H.K/2/pi;
            vdat.fc = H.startFreq + vdat.B/2;
            vdat.dt = 1/H.fs;
            vdat.er = 3.18;
            vdat.ci = 3e8/sqrt(vdat.er);
            vdat.lambdac = vdat.ci/vdat.fc;
            vdat.Nsamples = H.nchirpSamples;
            # Load each chirp into a row
            vdat.Endind = vdat.Startind + vdat.SamplesPerChirp - 1;

            vdat.vif = zeros(vdat.ChirpsInBurst,vdat.SamplesPerChirp); # preallocate array
            chirpInterval = 1.6384/(24*3600); # days
            for chirp = 1:vdat.ChirpsInBurst
                vdat.vif(chirp,:) = vdat.v(vdat.Startind(chirp):vdat.Endind(chirp));
                vdat.chirpNum(chirp,1) = chirp; # chirp number in burst
                vdat.chirpAtt(chirp,1) = AttSet(1+mod(chirp-1,numel(AttSet))); # attenuator setting for chirp
                vdat.chirpTime(chirp,1) = vdat.TimeStamp + chirpInterval*(chirp-1); # time of chirp
            end
        else
            vdat.er = 3.18;
            # Load each chirp into a row

            vdat.Endind = vdat.Startind + vdat.SamplesPerChirp - 1;
            vdat.vif = zeros(vdat.ChirpsInBurst,vdat.SamplesPerChirp); # preallocate array
            chirpInterval = 1.6384/(24*3600); # days
            for chirp = 1:vdat.ChirpsInBurst
                vdat.vif(chirp,:) = vdat.v(vdat.Startind(chirp):vdat.Endind(chirp));
                vdat.chirpNum(chirp,1) = chirp; # chirp number in burst
                vdat.chirpAtt(chirp,1) = AttSet(1+mod(chirp-1,numel(AttSet))); # attenuator setting for chirp
                vdat.chirpTime(chirp,1) = vdat.TimeStamp + chirpInterval*(chirp-1); # time of chirp
            end
            vdat.ChirpsInBurst = size(vdat.vif,1);
            vdat.SamplesPerChirp = size(vdat.vif,2);
            vdat.dt = 1/vdat.fs; # sample interval (s)
            vdat.T = (size(vdat.vif,2)-1)/vdat.fs; # period between first and last sample
            #vdat.T = size(vdat.vif,2)/vdat.fs; # period of sampling (cls test 26 aug 2014)
            # - this makes the amplitude of the fft centred at the right range, but phase wrong

            vdat.f1 = vdat.f0 + vdat.T*vdat.K/(2*pi); # stop frequency
            #vdat.f1 = vdat.f0 + vdat.dt*(vdat.SamplesPerChirp-1)*vdat.K/(2*pi); # stop frequency

            #vdat.B = vdat.f1-vdat.f0; # bandwidth (hz)
            #vdat.B = vdat.T*(vdat.K/(2*pi)); # bandwidth (hz)
            vdat.B = (size(vdat.vif,2)/vdat.fs)*(vdat.K/(2*pi)); # bandwidth (hz)

            vdat.fc = mean([vdat.f0 vdat.f1]); # Centre frequency
            #vdat.fc = vdat.f0 + vdat.B/2; # Centre frequency
            vdat.ci = 3e8/sqrt(vdat.er); # velocity in material
            vdat.lambdac = vdat.ci/vdat.fc; # Centre wavelength

        end
    else
        vdat.er = 3.18;
        vdat.dt = 1/vdat.fs;
        vdat.ci = 3e8/sqrt(vdat.er);
        vdat.lambdac = vdat.ci/vdat.fc;
        # Load each chirp into a row

        vdat.vif = zeros(vdat.ChirpsInBurst,vdat.SamplesPerChirp); # preallocate array
        chirpInterval = 1.6384/(24*3600); # days
        vdat.Endind = vdat.Startind + vdat.SamplesPerChirp - 1;
        for chirp = 1:vdat.ChirpsInBurst
            vdat.vif(chirp,:) = vdat.v(vdat.Startind(chirp):vdat.Endind(chirp));
            vdat.chirpNum(chirp,1) = chirp; # chirp number in burst
            vdat.chirpAtt(chirp,1) = AttSet(1+mod(chirp-1,numel(AttSet))); # attenuator setting for chirp
            vdat.chirpTime(chirp,1) = vdat.TimeStamp + chirpInterval*(chirp-1); # time of chirp
        end
    end

    # Create time and frequency stamp for samples
    vdat.t = vdat.dt*(0:size(vdat.vif,2)-1); # sampling times (rel to first)
    vdat.f = vdat.f0 + vdat.t.*vdat.K/(2*pi);

    # Calibrate
    #ca13 = [1 6]; # 2013
    #ca14 = [1 2]; # 2014
    #ca = [1 4];
    #vdat = fmcw_cal(vdat,ca13);

# --------------------------------------------------------------------------------------------

def load_burst_rmb(fn,burst,fs,version=5):
    """
    # vdat = LoadBurstRMB5(Filename, Burst, SamplesPerChirp)
    #
    # Read FMCW data file from after Oct 2014 (RMB2b + VAB Iss C, SW Issue >= 101)

    # Corrected so that Sampling Frequency has correct use (ie, not used in
    # this case)

    """
    MaxHeaderLen = 1500;
    burstpointer = 0;
    vdat.Code = 0;
    fid = fopen(Filename,'r');
    if fid >= 0
        fseek(fid,0,'eof');
        filelength = ftell(fid);
        BurstCount = 1;
        while BurstCount <= Burst && burstpointer <= filelength - MaxHeaderLen
            fseek(fid,burstpointer,'bof');
            A = fread(fid,MaxHeaderLen,'*char');
            A = A';       #'
            SearchString = 'N_ADC_SAMPLES=';
            searchind = strfind(A,SearchString);
            if ~isempty(searchind)
                try
                    searchCR = strfind(A(searchind(1):end),[char(13),char(10)]);
                    vdat.Nsamples = sscanf(A(searchind(1)+length(SearchString):searchCR(1)+searchind(1)),'#d');
                    WperChirpCycle = vdat.Nsamples;
                    SearchString = 'NSubBursts=';
                    searchind = strfind(A,SearchString);
                    searchCR = strfind(A(searchind(1):end),[char(13),char(10)]);
                    vdat.SubBurstsInBurst = sscanf(A(searchind(1)+length(SearchString):searchCR(1)+searchind(1)),'#d');

                    SearchString = 'Average=';
                    searchind = strfind(A, SearchString);
                    if isempty(searchind)
                        vdat.Average = 0; #cls 9/jan/14 -average not included in mooring deploy
                    else
                        searchCR = strfind(A(searchind(1):end),[char(13),char(10)]);
                        vdat.Average = sscanf(A(searchind(1)+length(SearchString):searchCR(1)+searchind(1)),'#d');
                    end

                    SearchString = 'nAttenuators=';
                    searchind = strfind(A, SearchString);
                    searchCR = strfind(A(searchind(1):end),[char(13),char(10)]);
                    vdat.NAttenuators = sscanf(A(searchind(1)+length(SearchString):searchCR(1)+searchind(1)),'#d',1);

                    SearchString = 'Attenuator1=';
                    searchind = strfind(A, SearchString);
                    searchCR = strfind(A(searchind(1):end),[char(13),char(10)]);
                    vdat.Attenuator_1 = sscanf(A(searchind(1)+length(SearchString):searchCR(1)+searchind(1)),'#f',vdat.NAttenuators);

                    SearchString = 'AFGain=';
                    searchind = strfind(A, SearchString);
                    searchCR = strfind(A(searchind(1):end),[char(13),char(10)]);
                    vdat.Attenuator_2 = sscanf(A(searchind(1)+length(SearchString):searchCR(1)+searchind(1)),'#f',vdat.NAttenuators);

                    SearchString = 'TxAnt=';
                    searchind = strfind(A, SearchString);
                    searchCR = strfind(A(searchind(1):end),[char(13),char(10)]);
                    vdat.TxAnt = sscanf(A(searchind(1)+length(SearchString):searchCR(1)+searchind(1)),'#d',8);

                    SearchString = 'RxAnt=';
                    searchind = strfind(A, SearchString);
                    searchCR = strfind(A(searchind(1):end),[char(13),char(10)]);
                    vdat.RxAnt = sscanf(A(searchind(1)+length(SearchString):searchCR(1)+searchind(1)),'#d',8);

                    ind = find(vdat.TxAnt~=1);
                    vdat.TxAnt(ind) = [];
                    ind = find(vdat.RxAnt~=1);
                    vdat.RxAnt(ind) = [];

                    if vdat.Average
                        vdat.ChirpsInBurst = 1;
                    else
                        vdat.ChirpsInBurst = vdat.SubBurstsInBurst * length(vdat.TxAnt) * ...
                           length(vdat.RxAnt) * vdat.NAttenuators;
                    end

                    SearchString = '*** End Header ***';
                    searchind = strfind(A, SearchString);

                    burstpointer = burstpointer + searchind(1) + length(SearchString);
                catch
                    vdat.Code = -2;
                    vdat.Burst = BurstCount;
                    keyboard
                    return
                end
            end
            WordsPerBurst = vdat.ChirpsInBurst * WperChirpCycle;
            if BurstCount < Burst && burstpointer <= filelength - MaxHeaderLen
                if vdat.Average
                    burstpointer = burstpointer + vdat.ChirpsInBurst * WperChirpCycle*4;
                else
                    burstpointer = burstpointer + vdat.ChirpsInBurst * WperChirpCycle*2;
                end
            end
            BurstCount = BurstCount + 1;
        end

        # Extract remaining information from header
        SearchString = 'Time stamp=';
        searchind = strfind(A, SearchString);
        if isempty(searchind)
            vdat.Code = -4;
            return
        end
        try
            searchCR = strfind(A(searchind(1):end),[char(13),char(10)]);
            td = sscanf(A(searchind(1)+length(SearchString):searchCR(1)+searchind(1)),...
                '#d-#d-#d #d:#d:#d');
            vdat.TimeStamp = datenum(td(1),td(2),td(3),td(4),td(5),td(6));
        catch err
            vdat.Code = 1;
        end

        SearchString = 'Temp1=';
        searchind = strfind(A, SearchString);
        try
            searchCR = strfind(A(searchind(1):end),[char(13),char(10)]);
            vdat.Temperature_1 = sscanf(A(searchind(1)+length(SearchString):searchCR(1)+searchind(1)),'#f');
        catch err
            vdat.Code = 1;
        end

        SearchString = 'Temp2=';
        searchind = strfind(A, SearchString);
        try
            searchCR = strfind(A(searchind(1):end),[char(13),char(10)]);
            vdat.Temperature_2 = sscanf(A(searchind(1)+length(SearchString):searchCR(1)+searchind(1)),'#f');
        catch err
            vdat.Code = 1;
        end

        SearchString = 'BatteryVoltage=';
        searchind = strfind(A, SearchString);
        try
            searchCR = strfind(A(searchind(1):end),[char(13),char(10)]);
            vdat.BatteryVoltage = sscanf(A(searchind(1)+length(SearchString):searchCR(1)+searchind(1)),'#f');
        catch err
            vdat.Code = 1;
        end


        fseek(fid,burstpointer-1,'bof');
        if BurstCount == Burst+1
            if vdat.Average == 2
                [vdat.v count] = fread(fid,WordsPerBurst,'*uint32','ieee-le');
            elseif vdat.Average == 1
                fseek(fid,burstpointer+1,'bof');
                [vdat.v count] = fread(fid,WordsPerBurst,'*real*4','ieee-le');
            else
                [vdat.v count] = fread(fid,WordsPerBurst,'*uint16','ieee-le');
            end
            if count < WordsPerBurst
                vdat.Code = 2;
            end
            vdat.v(vdat.v<0) = vdat.v(vdat.v<0) + 2^16;
            vdat.v = single(vdat.v);
            vdat.v = vdat.v * 2.5 / 2^16;
            if vdat.Average == 2
                vdat.v = vdat.v / (vdat.SubBurstsInBurst * vdat.NAttenuators);
            end
            vdat.Startind = (1:WperChirpCycle:WperChirpCycle*vdat.ChirpsInBurst)';     #'
            vdat.Endind = vdat.Startind + WperChirpCycle - 1;
            vdat.Burst = Burst;
        else
            # Too few bursts in file
            vdat.Burst = BurstCount - 1;
            vdat.Code = -4;
            #keyboard
        end
        fclose(fid);
    else
        # Unknown file
        vdat.Code = -1;
    end

    # Clean temperature record (wrong data type?)
    bti1 = find(vdat.Temperature_1>300);
    if ~isempty(bti1)
        vdat.Temperature_1(bti1) = vdat.Temperature_1(bti1)-512;
    end
    bti2 = find(vdat.Temperature_2>300);
    vdat.Temperature_2(bti2) = vdat.Temperature_2(bti2)-512;

# --------------------------------------------------------------------------------------------

def file_format(fn):
    """
    # Determine fmcw file format from burst header using keyword presence

    # Craig Stewart
    # 2013-10-20
    #
    # Updated by Keith Nicholls, 2014-10-22: RMB2
    """

    [fid, msg] = fopen(filename,'rt');
    if fid == -1
        error(msg)
    end
    MaxHeaderLen = 2000;
    A = fread(fid,MaxHeaderLen,'*char');
    fclose(fid);
    A = A';      #'
    if ~isempty(strfind(A, 'SW_Issue=')); # Data from RMB2 after Oct 2014
        fmt = 5;
    elseif ~isempty(strfind(A, 'SubBursts in burst:')); # Data from after Oct 2013
        fmt = 4;
    elseif ~isempty(strfind(A, '*** Burst Header ***')); # Data from Jan 2013
        fmt = 3;
    elseif ~isempty(strfind(A, 'RADAR TIME')); # Data from Prototype FMCW radar (nov 2012)
        fmt = 2;
    else
        #fmt = 0; # unknown file format
        error('Unknown file format - check file')
    end

# --------------------------------------------------------------------------------------------

def load_parameters_rmb(fn):
    """
    %Extract from the hex codes the actual paramaters used by RMB2
    %The contents of config.ini are copied into a data header.
    %Note this script assumes that the format of the hex codes have quotes
    %e.g. Reg02="0D1F41C8"

    %Checks for a sampling frequency of 40 or 80 KHz.  Apart from Lai Bun's
    %variant (WDC + Greenland) it could be hard coded to 40 KHz.

    %However, there is no check made by the system that the N_ADC_SAMPLES
    %matches the requested chirp length

    %NOT COMPLETE - needs a means of checking for profile mode, where multiple sweeps
    %per period are transmitted- see last line
    """

    H = struct;

    fsysclk = 1e9;
    H.fs = 4e4;
    % fprintf(1,'ASSUMPTIONS:DDS clock = %d\n',fsysclk);

    if nargin == 0
         [fileName, pathName] = uigetfile('*.dat','Choose data file');
         dataFile = [pathName fileName];
    end
    fid = fopen(dataFile,'rt');
    A = fread(fid,2000,'*char');
    A = A';      #'
    fclose(fid);
    loc1 = strfind(A,'Reg0');
    loc2 = strfind(A,'="');

    for k = 1:length(loc1)
       switch(A(loc1(k):loc2(k)))
           case 'Reg01=' %Control Function Register 2 (CFR2)�Address 0x01 Four bytes
            #Bit 19 (Digital ramp enable)= 1 = Enables digital ramp generator functionality.
            #Bit 18 (Digital ramp no-dwell high) 1 = enables no-dwell high functionality.
            #Bit 17 (Digital ramp no-dwell low) 1 = enables no-dwell low functionality.
            #With no-dwell high, a positive transition of the DRCTL pin initiates a positive slope ramp, which
            #continues uninterrupted (regardless of any activity on the DRCTL pin) until the upper limit is reached.
            #Setting both no-dwell bits invokes a continuous ramping mode of operation;
            loc3 = strfind(A(loc2(k)+2:end),'"');
            val = A((loc2(k)+2:loc2(k)+loc3(1)));
            val = dec2bin(hex2dec(val)); val = fliplr(val);
            H.noDwellHigh = str2num(val(18+1));
            H.noDwellLow = str2num(val(17+1));

    #        case 'Reg08' %Phase offset word Register (POW) Address 0x08. 2 Bytes dTheta = 360*POW/2^16.
    #         val = char(reg{1,2}(k));
    #         H.phaseOffsetDeg = hex2dec(val(1:4))*360/2^16;

           case 'Reg0B=' #Digital Ramp Limit Register Address 0x0B
            #63:32 Digital ramp upper limit 32-bit digital ramp upper limit value.
            #31:0 Digital ramp lower limit 32-bit digital ramp lower limit value.
             loc3 = strfind(A(loc2(k)+2:end),'"');
            val = A((loc2(k)+2:loc2(k)+loc3(1)));
            H.startFreq = hex2dec(val(9:end))*fsysclk/2^32;
            H.stopFreq = hex2dec(val(1:8))*fsysclk/2^32;

           case 'Reg0C='  #Digital Ramp Step Size Register Address 0x0C
            #63:32 Digital ramp decrement step size 32-bit digital ramp decrement step size value.
            #31:0 Digital ramp increment step size 32-bit digital ramp increment step size value.
            loc3 = strfind(A(loc2(k)+2:end),'"');
            val = A((loc2(k)+2:loc2(k)+loc3(1)));
            H.rampUpStep = hex2dec(val(9:end))*fsysclk/2^32;
            H.rampDownStep = hex2dec(val(1:8))*fsysclk/2^32;

           case 'Reg0D='  #Digital Ramp Rate Register Address 0x0D
            #31:16 Digital ramp negative slope rate 16-bit digital ramp negative slope value that defines the time interval between decrement values.
            #15:0 Digital ramp positive slope rate 16-bit digital ramp positive slope value that defines the time interval between increment values.
            loc3 = strfind(A(loc2(k)+2:end),'"');
            val = A((loc2(k)+2:loc2(k)+loc3(1)));
            H.tstepUp = hex2dec(val(5:end))*4/fsysclk;
            H.tstepDown = hex2dec(val(1:4))*4/fsysclk;
       end
    end

    loc = strfind(A,'SamplingFreqMode=');
    searchCR = strfind(A(loc(1):end),[char(10)]);
    H.fs = sscanf(A(loc(1)+length(['SamplingFreqMode=']):searchCR(1)+loc(1)),'%d\n');
    if H.fs == 1
        H.fs = 8e4;
    else
        H.fs = 4e4;
    end
    # if(H.fs > 70e3)
    #     H.fs = 80e3;
    # else
    #     H.fs = 40e3;
    # end

    loc = strfind(A,'N_ADC_SAMPLES=');
    searchCR = strfind(A(loc(1):end),[char(10)]);
    H.Nsamples = sscanf(A(loc(1)+length(['N_ADC_SAMPLES=']):searchCR(1)+loc(1)),'%d\n');

    H.nstepsDDS = round(abs((H.stopFreq - H.startFreq)/H.rampUpStep));%abs as ramp could be down
    H.chirpLength = H.nstepsDDS * H.tstepUp;
    H.nchirpSamples = round(H.chirpLength * H.fs);

    # If number of ADC samples collected is less than required to collect
    # entire chirp, set chirp length to length of series actually collected
    if H.nchirpSamples > H.Nsamples
        H.chirpLength = H.Nsamples / H.fs;
    end

    H.K = 2*pi*(H.rampUpStep/H.tstepUp); % chirp gradient (rad/s/s)
    if(H.stopFreq > 400e6)
        H.rampDir = 'down';
    else
        H.rampDir = 'up';
    end

    if(H.noDwellHigh && H.noDwellLow)
        H.rampDir = 'upDown';
        H.nchirpsPerPeriod = NaN;% H.nchirpSamples/(H.chirpLength);
    end